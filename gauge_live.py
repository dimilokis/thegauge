# -*- coding: utf-8 -*-
"""gauge_live.py — coleta dados ao vivo da Binance (spot, via data-api.binance.vision)
para as top-N moedas por volume 24h, calcula Gauge Score / Move / Driver / Verdict,
publica gauge_live.json e dispara alerta no Telegram quando um ativo entra em estado
extremo E independente de BTC.

Endpoint: data-api.binance.vision e o espelho publico oficial da Binance para
market data (sem chave, sem conta) e NAO sofre o geo-block HTTP 451 que a
fapi.binance.com aplica aos IPs de datacenter dos runners do GitHub Actions.

Sem lookahead: cada linha usa apenas dados ate o fechamento do dia mais recente.
Sem sobrevivencia: ranking por liquidez e recalculado a cada execucao, nao fixo."""
import os, json, time, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketing"))
from social_kit import add_hit  # noqa: E402

DATA_API = "https://data-api.binance.vision"
TOP_N = 100
KLINE_LIMIT = 120          # buffer > 90d para rolling windows
REF_SYMBOL = "BTCUSDT"
ALERT_SIGMA = 2.5          # "extreme" na definicao da landing page
ALERT_MAX_BTC_R2 = 0.40    # "independent" = pouco explicado por BTC

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(ROOT, "docs", "gauge_live.json")
STATE_JSON = os.path.join(ROOT, "alert_state.json")
META_CACHE_JSON = os.path.join(ROOT, "coin_meta_cache.json")
MOVE_STATE_JSON = os.path.join(ROOT, "move_tier_state.json")
ANALYTICS_LOG = os.path.join(ROOT, "analytics_log.jsonl")
NOTABLE_SIGMA = 1.0    # mesmo corte do moveTier() do dashboard (Normal/Notable/Extreme)

TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})


class GeoBlocked(Exception):
    """Binance recusou o IP do runner (HTTP 451). Com o data-api.binance.vision
    isso NAO deveria acontecer (endpoint publico de market data, sem geo-block);
    fica como rede de seguranca — se ocorrer, a proxima run horaria tenta de novo."""
COINGECKO = "https://api.coingecko.com/api/v3"


def log(msg):
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def load_meta_cache():
    """Cache persistente symbol -> {name, icon}, commitado no repo pelo
    workflow. E ele que garante que um nome resolvido uma vez NUNCA mais some
    do dashboard, mesmo que o CoinGecko rate-limite a run inteira. E um JSON
    editavel a mao: se algum ticker ambiguo casar com a moeda errada, corrigir
    a linha aqui resolve pra sempre."""
    try:
        raw = json.load(open(META_CACHE_JSON))
        return {k: v for k, v in raw.items() if isinstance(v, dict) and v.get("name")}
    except Exception:
        return {}


def save_meta_cache(cache):
    json.dump(cache, open(META_CACHE_JSON, "w"), indent=1, sort_keys=True)


def fetch_coin_meta(pages=8):
    """Nome completo + icone via CoinGecko (fonte real, sem inventar nada).
    8 paginas de 250 = top-2000 por market cap, porque o Gauge ranqueia por
    VOLUME e varias moedas de volume alto tem market cap la embaixo (PUNDIX
    #775, HEI #1153, Sleepless AI #1999...). Guarda TODOS os candidatos de
    cada ticker (em ordem de market cap) com o preco — a desambiguacao por
    preco acontece no lookup_meta. Rate limit (429) ganha retry com espera;
    falha definitiva devolve o que ja juntou — nunca derruba o pipeline,
    o cache persistente cobre o resto."""
    meta = {}
    for page in range(1, pages + 1):
        for attempt in range(3):
            try:
                r = SESSION.get(
                    COINGECKO + "/coins/markets",
                    params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page},
                    timeout=15,
                )
                data = r.json()
                if isinstance(data, list):
                    for c in data:
                        sym = c["symbol"].upper()
                        meta.setdefault(sym, []).append(
                            {"name": c["name"], "icon": c["image"], "price": c.get("current_price")}
                        )
                    break
                log("CoinGecko pagina {} respondeu {} (tentativa {}/3) — aguardando 25s.".format(
                    page, r.status_code, attempt + 1))
            except Exception as e:
                log("CoinGecko pagina {} falhou ({}) (tentativa {}/3) — aguardando 25s.".format(
                    page, e, attempt + 1))
            time.sleep(25)
        time.sleep(1.5)
    return meta


# Prefixos que a Binance poe em moedas de preco microscopico (1000SHIB = mil
# SHIB por contrato). O CoinGecko conhece a moeda pelo ticker puro; o fator
# converte o preco do CoinGecko pra escala do par da Binance.
BINANCE_PREFIXES = (("1000000", 1e6), ("1000", 1e3), ("1M", 1e6))

# Tolerancia da desambiguacao por preco: |log(preco_binance/preco_cg)| < 0.2
# (~±22%). A licao que motivou isso: a Binance recicla tickers — "AI" hoje e
# Sleepless AI ($0.021), mas o CoinGecko tambem tem Gensyn com ticker AI
# ($0.026, market cap maior). Escolher por ranking pegava a moeda ERRADA;
# o preco identifica a certa sem ambiguidade.
PRICE_LOG_TOL = 0.2


def _price_matches(binance_price, cg_price, factor=1.0):
    if not cg_price or not binance_price:
        return None  # sem preco pra comparar — nem confirma nem nega
    return abs(np.log(binance_price / (cg_price * factor))) < PRICE_LOG_TOL


def lookup_meta(meta, symbol, binance_price):
    """Resolve o ticker da Binance num candidato do CoinGecko. Regra: se ha
    preco pra comparar, so aceita candidato cujo preco bate com o da Binance;
    um candidato sem preco no CoinGecko so e aceito se for o unico do ticker
    (sem colisao = sem risco de pegar a moeda errada)."""
    variants = [(symbol, 1.0)]
    for pref, factor in BINANCE_PREFIXES:
        if symbol.startswith(pref):
            variants.append((symbol[len(pref):], factor))
    for key, factor in variants:
        candidates = meta.get(key, [])
        for c in candidates:
            ok = _price_matches(binance_price, c["price"], factor)
            if ok or (ok is None and len(candidates) == 1):
                return {"name": c["name"], "icon": c["icon"]}
    return None


def search_coin_meta(symbol):
    """Fallback pra moedas fora do top-2000 por market cap (o /coins/markets
    nao cobre). Busca direcionada por simbolo — sem inventar nada. Tenta
    tambem o ticker sem prefixo da Binance (1MBABYDOGE -> BABYDOGE). O /search
    nao devolve preco, entao aqui nao da pra desambiguar por preco: se o
    ticker tiver colisao, fica com a de menor market_cap_rank — se casar
    errado, corrigir a mao no coin_meta_cache.json (que tem prioridade quando
    o match por preco nao resolve). Rate limit (429) ganha retry com espera."""
    queries = [symbol]
    for pref, _factor in BINANCE_PREFIXES:
        if symbol.startswith(pref) and symbol[len(pref):] not in queries:
            queries.append(symbol[len(pref):])
    for query in queries:
        for _ in range(2):
            try:
                r = SESSION.get(COINGECKO + "/search", params={"query": query}, timeout=15)
                if r.status_code == 429:
                    log("CoinGecko /search rate-limited em {} — aguardando 30s.".format(query))
                    time.sleep(30)
                    continue
                data = r.json()
                coins = data.get("coins", []) if isinstance(data, dict) else []
                matches = [c for c in coins if c.get("symbol", "").upper() == query]
                if matches:
                    matches.sort(key=lambda c: c.get("market_cap_rank") if c.get("market_cap_rank") is not None else 10**9)
                    best = matches[0]
                    return {"name": best["name"], "icon": best.get("large") or best.get("thumb")}
                break
            except Exception:
                break
    return None


# Pares USDT que nao sao "cripto de verdade" para um screener: stablecoins
# (score/sigma de um peg nao significa nada), fiat tokenizado, ouro tokenizado
# e wrapped de BTC/ETH (duplicaria o proprio BTC/ETH no ranking).
NOT_REAL_CRYPTO = {
    "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "PYUSD", "USD1", "USDE",
    "XUSD", "AEUR", "EUR", "EURI", "GBP", "TRY", "BRL", "ARS", "COP", "UAH",
    "PAXG", "XAUT", "WBTC", "WBETH", "WETH", "BETH", "STETH",
    "RLUSD",  # Ripple USD (stablecoin)
    "U",      # United Stables (stablecoin) -- achado 13/jul via analytics log:
              # sigma alto num ativo travado em $1 e ruido puro, nao movimento real
}

# Acoes e ETFs tokenizados que a Binance lista no spot com sufixo "B"
# (NVDAB = NVIDIA, SPYB = SPY etc). O spot NAO expoe o campo underlyingType
# que o Futures tinha, entao a exclusao e por lista explicita. Levantada em
# 2026-07 com: exchangeInfo -> baseAsset USDT terminando em "B", separando as
# criptos legitimas (ARB, BNB, SHIB, CKB, DGB, TRB, BB, YB). Se um dia surgir
# uma "acao" no dashboard, e porque a Binance listou um ticker novo — repetir
# o levantamento e adicionar aqui.
TOKENIZED_EQUITIES = {
    "AMDB", "CBRSB", "COINB", "CRCLB", "DRAMB", "EWYB", "GLWB", "GOOGLB",
    "INTCB", "LITEB", "METAB", "MSFTB", "MSTRB", "MUB", "NBISB", "NVDAB",
    "PLTRB", "QCOMB", "QQQB", "SNDKB", "SOXLB", "SPCXB", "SPYB", "TSLAB",
    "WDCB",
}
NOT_REAL_CRYPTO |= TOKENIZED_EQUITIES


def get_top_symbols(n=TOP_N, buffer=40):
    """Ranking por volume de 24h, recalculado a cada run — sem lista fixa.
    Universo = so cripto de verdade: no spot a Binance tambem lista stablecoins,
    fiat e ouro tokenizados e wrapped tokens; nada disso pertence a um screener
    de cripto, entao filtramos pela blocklist NOT_REAL_CRYPTO (no Futures o
    filtro era underlyingType == COIN; o spot nao expoe esse campo).

    Devolve os top-n por volume MAIS um buffer de reserva (proximos por
    ranking) — o buffer so e usado em build_snapshot() se algum dos top-n
    falhar ao buscar klines, pra nao encolher o universo publicado por causa
    de uma falha pontual de rede/rate-limit num simbolo especifico."""
    r_ex = SESSION.get(DATA_API + "/api/v3/exchangeInfo", timeout=20)
    ex = r_ex.json()
    if "symbols" not in ex:
        if r_ex.status_code == 451:
            raise GeoBlocked(
                "Binance bloqueou o IP deste runner (HTTP 451, restricao geografica/datacenter)."
            )
        raise RuntimeError(
            "exchangeInfo sem 'symbols' -- HTTP {} -- resposta da Binance: {}".format(
                r_ex.status_code, str(ex)[:500]
            )
        )
    crypto = {
        s["symbol"] for s in ex["symbols"]
        if s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
        and s.get("isSpotTradingAllowed", True)
        and s.get("baseAsset") not in NOT_REAL_CRYPTO
    }
    r_tk = SESSION.get(DATA_API + "/api/v3/ticker/24hr", timeout=20)
    d = r_tk.json()
    if not isinstance(d, list):
        raise RuntimeError(
            "ticker/24hr nao veio como lista -- HTTP {} -- resposta da Binance: {}".format(
                r_tk.status_code, str(d)[:500]
            )
        )
    rows = [x for x in d if x["symbol"] in crypto]
    rows.sort(key=lambda x: -float(x["quoteVolume"]))
    symbols = [x["symbol"] for x in rows[:n]]
    reserve = [x["symbol"] for x in rows[n:n + buffer]]
    if REF_SYMBOL not in symbols:
        symbols.append(REF_SYMBOL)
    return symbols, reserve


def get_daily_klines(symbol, limit=KLINE_LIMIT):
    r = SESSION.get(
        DATA_API + "/api/v3/klines",
        params={"symbol": symbol, "interval": "1d", "limit": limit},
        timeout=20,
    )
    if r.status_code != 200:
        return None
    rows = r.json()
    if not isinstance(rows, list) or len(rows) < 40:
        return None
    close = np.array([float(x[4]) for x in rows], dtype=np.float64)
    vol = np.array([float(x[7]) for x in rows], dtype=np.float64)  # quote volume
    return close, vol


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = np.clip(d, 0, None)
    dn = np.clip(-d, 0, None)
    a = 2.0 / (n + 1)

    def ema(x):
        o = np.empty_like(x)
        o[0] = x[0]
        for i in range(1, len(x)):
            o[i] = a * x[i] + (1 - a) * o[i - 1]
        return o

    ru, rd = ema(up), ema(dn)
    rs = ru / (rd + 1e-12)
    return 100 * rs / (1 + rs)


def gauge_score_series(close):
    s = pd.Series(close)
    mn = s.rolling(90, min_periods=20).min().to_numpy()
    mx = s.rolling(90, min_periods=20).max().to_numpy()
    pct = np.where(mx > mn, (close - mn) / (mx - mn + 1e-12) * 100, 50.0)
    r = rsi(close)
    ma = s.rolling(50, min_periods=10).mean().to_numpy()
    madist = np.clip(50 + (close / ma - 1) * 250, 0, 100)
    return 0.5 * pct + 0.3 * r + 0.2 * madist


def move_sigma(close):
    """z-score do |retorno| de hoje vs a distribuicao de |retornos| dos 90d ANTERIORES
    (o proprio hoje fica fora da regua que mede o hoje — sem contaminacao)."""
    ret = np.diff(close) / close[:-1]
    absret = np.abs(ret)
    if len(absret) < 21:
        return 0.0
    baseline = absret[:-1][-90:]
    mu, sd = baseline.mean(), baseline.std()
    if sd < 1e-9:
        return 0.0
    return float((absret[-1] - mu) / sd)


def btc_r2(coin_close, btc_close, window=30):
    """R^2 dos retornos da moeda explicados pelos retornos do BTC (regressao linear
    simples, janela rolante). Metrica sempre bem definida, sem depender do sinal do
    movimento do dia (diferente de tentar atribuir % de um unico candle)."""
    n = min(len(coin_close), len(btc_close))
    if n < window + 1:
        window = n - 1
    if window < 10:
        return 0.5
    cr = np.diff(coin_close[-window - 1:]) / coin_close[-window - 1:-1]
    br = np.diff(btc_close[-window - 1:]) / btc_close[-window - 1:-1]
    if br.std() < 1e-9 or cr.std() < 1e-9:
        return 0.0
    corr = np.corrcoef(cr, br)[0, 1]
    if np.isnan(corr):
        return 0.0
    return float(np.clip(corr ** 2, 0, 1))


def liquidity_tier(vol):
    """Tier de liquidez sustentada (mediana do dollar-volume dos 90d
    ANTERIORES a hoje, sem contar o dia de hoje — mesma metodologia do
    backtest historico bot/_gauge_hist_backtest.py). Cortes calibrados
    contra 400k dias-moeda 2020-2026: A/B tem N grande e formato de
    momentum; C/D tem N menor e formato mais equilibrado.

    `vol` aqui e o QUOTE volume do kline (campo 7) — ja em dolares. BUG
    historico corrigido em 13/jul/2026: o codigo fazia close*vol em cima do
    quote volume, multiplicando o preco DUAS vezes — moeda barata (SHIB,
    PEPE, DOGE) tinha o dollar-volume esmagado e caia pra tier C/D errado,
    distorcendo o verdict (que e tier-aware). O backtest que calibrou os
    cortes fazia close*volume_BASE (correto); quote volume direto e a mesma
    grandeza."""
    dollar_vol = vol
    if len(dollar_vol) < 21:
        return "D"
    baseline = dollar_vol[:-1][-90:]
    med = float(np.median(baseline))
    if med >= 50e6:
        return "A"
    if med >= 10e6:
        return "B"
    if med >= 2e6:
        return "C"
    return "D"


def verdict(score, tier):
    """Verdict calibrado por tier — achado do backtest historico (400k
    dias-moeda, 2020-2026): em tiers liquidas (A/B), score alto e sinal de
    MOMENTUM (a moeda continua subindo), nao de reversao — chamar isso de
    'Overbought' seria prometer uma reversao que os dados nao confirmam.
    So a faixa mais extrema do lado baixo (score<10) mostrou reversao real
    e estatisticamente significativa nessas tiers. Tiers C/D mantem a
    leitura tradicional, mais equilibrada nos dados."""
    if tier in ("A", "B"):
        if score < 10:
            return "Oversold"
        if score > 70:
            return "Strong Uptrend"
        return "Neutral"
    if score < 30:
        return "Oversold"
    if score > 70:
        return "Overbought"
    return "Neutral"


def build_snapshot():
    symbols, reserve = get_top_symbols()
    target = len(symbols)
    log("Universo: {} simbolos (ranking por volume 24h), {} de reserva".format(target, len(reserve)))

    data = {}
    failed = []
    for i, sym in enumerate(symbols):
        kl = get_daily_klines(sym)
        if kl is None:
            failed.append(sym)
            continue
        close, vol = kl
        data[sym] = {"close": close, "vol": vol}
        time.sleep(0.08)  # gentil com o rate limit
        if (i + 1) % 25 == 0:
            log("  ... {}/{} coletados".format(i + 1, len(symbols)))

    if failed:
        log("Falha ao buscar klines de {}: {} -- tentando preencher com reserva".format(len(failed), failed))
        for sym in reserve:
            if len(data) >= target:
                break
            if sym in data:
                continue
            kl = get_daily_klines(sym)
            if kl is None:
                continue
            close, vol = kl
            data[sym] = {"close": close, "vol": vol}
            time.sleep(0.08)
        log("Apos reserva: {} simbolos coletados (meta {})".format(len(data), target))

    if REF_SYMBOL not in data:
        raise RuntimeError("Nao foi possivel coletar dados do BTC — abortando run.")
    btc_close = data[REF_SYMBOL]["close"]

    meta_cache = load_meta_cache()
    # A varredura de 8 paginas do CoinGecko (com retry em 429) so roda 1x/dia —
    # rodar isso toda run e' o que fazia cada execucao do Actions demorar
    # minutos a mais em espera de rate-limit. Com o cron de 15/15min (4
    # runs/hora) so a PRIMEIRA run da hora 0 (minuto<15) faz o scan
    # completo — checar so a hora dispararia 4x seguidas as 00h. Nas outras
    # runs, o cache persistente ja resolve quase tudo; search_coin_meta cobre
    # o raro caso de symbol novo que ainda nao esta no cache.
    now = datetime.now(timezone.utc)
    do_full_meta_scan = now.hour == 0 and now.minute < 15
    coin_meta = fetch_coin_meta() if do_full_meta_scan else {}
    if not do_full_meta_scan:
        log("Scan completo do CoinGecko pulado nesta run (so roda as 00h UTC) — usando cache.")

    rows = []
    for sym, d in data.items():
        close = d["close"]
        if len(close) < 40:
            continue
        vol = d["vol"]
        score = float(gauge_score_series(close)[-1])
        sigma = move_sigma(close)
        is_market = sym == REF_SYMBOL
        r2 = 1.0 if is_market else btc_r2(close, btc_close)
        from_btc_pct = round(r2 * 100)
        ret_pct = float((close[-1] / close[-2] - 1) * 100) if len(close) >= 2 else 0.0
        base_symbol = sym.replace("USDT", "")
        tier = "A" if is_market else liquidity_tier(vol)
        # Prioridade: match com preco conferido > cache persistente > busca.
        meta = lookup_meta(coin_meta, base_symbol, float(close[-1]))
        if meta is None:
            meta = meta_cache.get(base_symbol)
        if meta is None:
            meta = search_coin_meta(base_symbol)
            time.sleep(1.5)
        rows.append({
            "symbol": base_symbol,
            "name": meta["name"] if meta else None,
            "icon": meta["icon"] if meta else None,
            "price": float(close[-1]),
            "ret_pct": round(ret_pct, 2),
            "score": round(score, 1),
            "sigma": round(sigma, 2),
            "from_btc_pct": from_btc_pct,
            "tier": tier,
            "is_market": is_market,
            "verdict": "Neutral" if is_market else verdict(score, tier),
        })

    for row in rows:
        if row["name"] and row["icon"]:
            meta_cache[row["symbol"]] = {"name": row["name"], "icon": row["icon"]}
    save_meta_cache(meta_cache)
    still_missing = [row["symbol"] for row in rows if not row["name"] or not row["icon"]]
    if still_missing:
        log("AVISO: {} ativo(s) SEM nome/icone nesta run (CoinGecko nao resolveu): {}".format(
            len(still_missing), still_missing))

    rows.sort(key=lambda r: -r["sigma"])
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(rows),
        "assets": rows,
    }
    return snapshot


def load_state():
    try:
        return set(json.load(open(STATE_JSON)))
    except Exception:
        return set()


def save_state(alerted):
    os.makedirs(os.path.dirname(STATE_JSON) or ".", exist_ok=True)
    json.dump(sorted(alerted), open(STATE_JSON, "w"))


def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT:
        log("Telegram nao configurado (faltam TG_BOT_TOKEN/TG_CHAT_ID) — pulando envio.")
        return
    url = "https://api.telegram.org/bot{}/sendMessage".format(TG_TOKEN)
    try:
        SESSION.post(url, data={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        log("Falha ao enviar Telegram: {}".format(e))


def send_telegram_photo(photo_path, caption):
    """Manda o card ja pronto como foto (nao so texto) -- o alerta e' o
    proprio card que vai pro thegauge.art/social.html mais tarde, so que
    chega na hora, direto no upload multipart (nao depende do commit/push
    do Actions nem do Cloudflare ja ter propagado o arquivo)."""
    if not TG_TOKEN or not TG_CHAT:
        log("Telegram nao configurado (faltam TG_BOT_TOKEN/TG_CHAT_ID) — pulando envio.")
        return
    url = "https://api.telegram.org/bot{}/sendPhoto".format(TG_TOKEN)
    try:
        with open(photo_path, "rb") as f:
            SESSION.post(
                url,
                data={"chat_id": TG_CHAT, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=30,
            )
    except Exception as e:
        log("Falha ao enviar foto Telegram: {}".format(e))


def process_alerts(snapshot):
    """Roda a cada execucao (a cada 15min). Ativo que ENTRA em estado
    extremo+independente agora mesmo ganha card na hora (social_kit.add_hit)
    e alerta no Telegram com a imagem anexada — nao espera nenhum horario
    fixo. O card acumula em docs/social/<hoje>/ junto com os outros que ja
    apareceram no dia (nao sobrescreve)."""
    prev = load_state()
    now_extreme = set()
    for a in snapshot["assets"]:
        if a["is_market"]:
            continue
        is_extreme_independent = abs(a["sigma"]) >= ALERT_SIGMA and a["from_btc_pct"] <= ALERT_MAX_BTC_R2 * 100
        if is_extreme_independent:
            now_extreme.add(a["symbol"])
            if a["symbol"] not in prev:
                caption = (
                    "<b>{}</b> — {} · Extreme\n"
                    "Move: {:.1f}σ · only {}% from BTC\n"
                    "Score {} — this move looks like its own thing.".format(
                        a["symbol"], a["verdict"], a["sigma"], a["from_btc_pct"], a["score"]
                    )
                )
                try:
                    png_path = add_hit(a)
                    send_telegram_photo(png_path, caption)
                except Exception as e:
                    log("Falha ao gerar card de {} ({}) — mandando so texto.".format(a["symbol"], e))
                    send_telegram(caption)
    save_state(now_extreme)


def move_tier(sigma):
    a = abs(sigma)
    if a >= ALERT_SIGMA:
        return "Extreme"
    if a >= NOTABLE_SIGMA:
        return "Notable"
    return "Normal"


TIER_RANK = {"Normal": 0, "Notable": 1, "Extreme": 2}


def log_analytics_events(snapshot):
    """Registra (append-only, NUNCA reescreve) toda vez que um ativo ENTRA
    em Notable ou Extreme vindo de um nivel mais baixo — nao a cada run que
    ele continua la (senao um ativo parado 3h em Extreme viraria 12 linhas
    identicas). Objetivo: dataset prospectivo pra medir honestamente "o que
    aconteceu depois" de cada alerta, sem lookahead (por construcao — cada
    linha so pode ser escrita depois que o proprio evento aconteceu) e sem
    cherry-pick (loga TUDO que cruza o limiar, nao so o que "deu certo").
    Inclui BTC/mercado (is_market) e ativos dependentes do BTC tambem —
    filtragem por independencia fica pra hora da analise, nao da coleta."""
    try:
        prev_tier = json.load(open(MOVE_STATE_JSON, encoding="utf-8"))
    except Exception:
        prev_tier = {}

    now_tier = {}
    new_lines = []
    ts = datetime.now(timezone.utc).isoformat()
    for a in snapshot["assets"]:
        tier = move_tier(a["sigma"])
        now_tier[a["symbol"]] = tier
        was = prev_tier.get(a["symbol"], "Normal")
        if TIER_RANK[tier] > TIER_RANK.get(was, 0):
            new_lines.append(json.dumps({
                "ts": ts, "symbol": a["symbol"], "name": a.get("name"),
                "move_tier": tier, "sigma": a["sigma"], "from_btc_pct": a["from_btc_pct"],
                "independent": a["from_btc_pct"] <= ALERT_MAX_BTC_R2 * 100,
                "verdict": a["verdict"], "score": a["score"], "liquidity_tier": a["tier"],
                "price": a["price"], "ret_pct": a["ret_pct"], "is_market": a["is_market"],
            }, ensure_ascii=False))

    if new_lines:
        with open(ANALYTICS_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        log("Analytics: {} novo(s) evento(s) Notable/Extreme registrado(s).".format(len(new_lines)))

    json.dump(now_tier, open(MOVE_STATE_JSON, "w"))


def main():
    snapshot = build_snapshot()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(snapshot, open(OUT_JSON, "w"), indent=2)
    n_meta = sum(1 for a in snapshot["assets"] if a.get("name"))
    log("Snapshot salvo: {} ({} ativos, {} com nome/icone)".format(OUT_JSON, snapshot["universe_size"], n_meta))
    process_alerts(snapshot)
    log_analytics_events(snapshot)
    log("Done.")


if __name__ == "__main__":
    try:
        main()
    except GeoBlocked as e:
        log("PULADO (nao e bug): {}".format(e))
        log("A proxima execucao horaria tenta de novo com outro IP.")
        sys.exit(0)
    except Exception as e:
        log("ERRO: {}".format(e))
        sys.exit(1)
