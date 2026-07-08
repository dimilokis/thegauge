# -*- coding: utf-8 -*-
"""gauge_live.py — coleta dados ao vivo da Binance Futures para as top-N moedas
por volume 24h, calcula Gauge Score / Move / Driver / Verdict, publica gauge_live.json
e dispara alerta no Telegram quando um ativo entra em estado extremo E independente de BTC.

Sem lookahead: cada linha usa apenas dados ate o fechamento do dia mais recente.
Sem sobrevivencia: ranking por liquidez e recalculado a cada execucao, nao fixo."""
import os, json, time, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests

FAPI = "https://fapi.binance.com"
TOP_N = 100
KLINE_LIMIT = 120          # buffer > 90d para rolling windows
REF_SYMBOL = "BTCUSDT"
ALERT_SIGMA = 2.5          # "extreme" na definicao da landing page
ALERT_MAX_BTC_R2 = 0.40    # "independent" = pouco explicado por BTC

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(ROOT, "public", "gauge_live.json")
STATE_JSON = os.path.join(ROOT, "alert_state.json")

TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

SESSION = requests.Session()


def log(msg):
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def get_top_symbols(n=TOP_N):
    """Ranking por volume de 24h (USDT perpetuals), recalculado a cada run — sem lista fixa."""
    d = SESSION.get(FAPI + "/fapi/v1/ticker/24hr", timeout=20).json()
    rows = [x for x in d if x["symbol"].endswith("USDT")]
    rows.sort(key=lambda x: -float(x["quoteVolume"]))
    symbols = [x["symbol"] for x in rows[:n]]
    if REF_SYMBOL not in symbols:
        symbols.append(REF_SYMBOL)
    return symbols


def get_daily_klines(symbol, limit=KLINE_LIMIT):
    r = SESSION.get(
        FAPI + "/fapi/v1/klines",
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
    """z-score do |retorno| de hoje vs a distribuicao de |retornos| dos ultimos 90d."""
    ret = np.diff(close) / close[:-1]
    absret = np.abs(ret)
    if len(absret) < 20:
        return 0.0
    window = absret[-90:] if len(absret) > 90 else absret
    mu, sd = window.mean(), window.std()
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


def verdict(score):
    if score < 30:
        return "Oversold"
    if score > 70:
        return "Overbought"
    return "Neutral"


def build_snapshot():
    symbols = get_top_symbols()
    log("Universo: {} simbolos (ranking por volume 24h)".format(len(symbols)))

    data = {}
    for i, sym in enumerate(symbols):
        kl = get_daily_klines(sym)
        if kl is None:
            continue
        close, vol = kl
        data[sym] = {"close": close, "vol": vol}
        time.sleep(0.08)  # gentil com o rate limit
        if (i + 1) % 25 == 0:
            log("  ... {}/{} coletados".format(i + 1, len(symbols)))

    if REF_SYMBOL not in data:
        raise RuntimeError("Nao foi possivel coletar dados do BTC — abortando run.")
    btc_close = data[REF_SYMBOL]["close"]

    rows = []
    for sym, d in data.items():
        close = d["close"]
        if len(close) < 40:
            continue
        score = float(gauge_score_series(close)[-1])
        sigma = move_sigma(close)
        is_market = sym == REF_SYMBOL
        r2 = 1.0 if is_market else btc_r2(close, btc_close)
        from_btc_pct = round(r2 * 100)
        rows.append({
            "symbol": sym.replace("USDT", ""),
            "score": round(score, 1),
            "sigma": round(sigma, 2),
            "from_btc_pct": from_btc_pct,
            "is_market": is_market,
            "verdict": "Neutral" if is_market else verdict(score),
        })

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


def process_alerts(snapshot):
    prev = load_state()
    now_extreme = set()
    for a in snapshot["assets"]:
        if a["is_market"]:
            continue
        is_extreme_independent = abs(a["sigma"]) >= ALERT_SIGMA and a["from_btc_pct"] <= ALERT_MAX_BTC_R2 * 100
        if is_extreme_independent:
            now_extreme.add(a["symbol"])
            if a["symbol"] not in prev:
                send_telegram(
                    "<b>{}</b> — {} · {}\n"
                    "Move: {:.1f}σ · only {}% from BTC\n"
                    "Score {} — this move looks like its own thing.".format(
                        a["symbol"], a["verdict"], "Extreme", a["sigma"], a["from_btc_pct"], a["score"]
                    )
                )
    save_state(now_extreme)


def main():
    snapshot = build_snapshot()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(snapshot, open(OUT_JSON, "w"), indent=2)
    log("Snapshot salvo: {} ({} ativos)".format(OUT_JSON, snapshot["universe_size"]))
    process_alerts(snapshot)
    log("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("ERRO: {}".format(e))
        sys.exit(1)
