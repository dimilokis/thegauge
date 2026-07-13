# -*- coding: utf-8 -*-
"""analytics_report.py — le analytics_log.jsonl (todo evento Notable/Extreme
registrado ao vivo por gauge_live.py, sem lookahead por construcao: cada
linha so existe pq o proprio evento ja aconteceu) e calcula o retorno
forward real, direto do historico publico da Binance (nao precisa ter
ficado "escutando" o preco em tempo real -- o preco de qualquer momento
passado sempre da pra buscar depois).

Roda a qualquer momento (nao precisa de agendamento):
    python analytics_report.py

Honestidade: reporta N por categoria e horizonte. Categoria/horizonte com
N pequeno mostra o numero mesmo assim, mas com aviso -- nunca esconde uma
celula so por dar numero feio, e nunca finge que um N=3 significa algo.
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT, "analytics_log.jsonl")
DATA_API = "https://data-api.binance.vision"
MIN_N_TRUST = 20  # abaixo disso, mostra o numero mas com aviso explicito

HORIZONS = [
    ("1h", timedelta(hours=1), "1h"),
    ("6h", timedelta(hours=6), "1h"),
    ("24h", timedelta(hours=24), "1h"),
    ("3d", timedelta(days=3), "1d"),
    ("7d", timedelta(days=7), "1d"),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})


def load_events():
    if not os.path.exists(LOG_PATH):
        return []
    events = []
    for line in open(LOG_PATH, encoding="utf-8"):
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


INTERVAL_MS = {"1h": 3600_000, "1d": 86_400_000}


def price_at(symbol, when, interval):
    """Preco (close) da barra da Binance mais proxima de `when`. Funciona
    pra qualquer momento passado -- e' assim que da pra medir o forward
    return sem ter guardado o preco em tempo real, so o timestamp do
    evento. Janela de busca escala com o tamanho da propria vela (bug
    achado 13/jul: janela fixa de 3h nao cobria uma vela DIARIA, que pode
    abrir bem mais de 3h antes do alvo -- sempre voltava None pra 1d)."""
    ms = int(when.timestamp() * 1000)
    step = INTERVAL_MS[interval]
    try:
        r = SESSION.get(
            DATA_API + "/api/v3/klines",
            params={"symbol": symbol + "USDT", "interval": interval,
                    "startTime": ms - 3 * step, "endTime": ms + step, "limit": 5},
            timeout=15,
        )
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return None
        # pega a barra cujo open_time e' o mais proximo (<=) de `when`
        best = None
        for row in rows:
            if row[0] <= ms:
                best = row
        if best is None:
            best = rows[0]
        return float(best[4])
    except Exception:
        return None


def main():
    events = load_events()
    if not events:
        print("Nenhum evento registrado ainda -- o log comeca a encher a partir de hoje.")
        return

    now = datetime.now(timezone.utc)
    print("Total de eventos no log: {}".format(len(events)))
    print("Primeiro evento: {}".format(events[0]["ts"]))
    print("Ultimo evento:   {}".format(events[-1]["ts"]))
    print()

    # agrupa por (move_tier, independent, direcao do sigma)
    groups = {}
    for e in events:
        key = (e["move_tier"], e["independent"], "up" if e["sigma"] >= 0 else "down")
        groups.setdefault(key, []).append(e)

    for key, evs in sorted(groups.items()):
        tier, indep, direction = key
        print("--- {} | independente={} | direcao={} (N={}) ---".format(tier, indep, direction, len(evs)))
        for hname, hdelta, interval in HORIZONS:
            rets = []
            for e in evs:
                ts = datetime.fromisoformat(e["ts"])
                target = ts + hdelta
                if target > now:
                    continue  # ainda nao deu tempo
                p1 = price_at(e["symbol"], target, interval)
                if p1 is None or not e.get("price"):
                    continue
                rets.append(p1 / e["price"] - 1)
                time.sleep(0.05)
            if not rets:
                print("  {:>4}: ainda sem eventos com tempo suficiente decorrido.".format(hname))
                continue
            n = len(rets)
            mean = sum(rets) / n * 100
            hit = sum(1 for r in rets if r > 0) / n * 100
            warn = "  (N baixo, so olhar daqui uns dias)" if n < MIN_N_TRUST else ""
            print("  {:>4}: N={:<4d} mean={:+6.2f}% hit={:5.1f}%{}".format(hname, n, mean, hit, warn))
        print()


if __name__ == "__main__":
    main()
