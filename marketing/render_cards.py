# -*- coding: utf-8 -*-
"""render_cards.py — ferramenta manual: forca a (re)geracao dos cards de hoje
a partir do snapshot local (docs/gauge_live.json), pra testar/backfill sem
esperar o proximo alerta de gauge_live.py disparar de verdade.

Em producao os cards SAO gerados automaticamente — cada run de gauge_live.py
chama social_kit.add_hit() na hora que um ativo entra em estado extremo
(ver process_alerts() em gauge_live.py). Isso aqui so re-roda esse mesmo
caminho pros hits atuais, sem duplicar logica."""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from social_kit import add_hit

ROOT = os.path.dirname(os.path.abspath(__file__))
GAUGE_ROOT = os.path.dirname(ROOT)
JSON_PATH = os.path.join(GAUGE_ROOT, "docs", "gauge_live.json")


def log(msg):
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def main():
    d = json.load(open(JSON_PATH, encoding="utf-8"))
    A = [a for a in d["assets"] if not a["is_market"]]
    hits = sorted([a for a in A if abs(a["sigma"]) >= 2.5 and a["from_btc_pct"] <= 40],
                  key=lambda a: -abs(a["sigma"]))

    if not hits:
        log("Nenhum outlier no snapshot atual — nada pra gerar.")
        return

    for a in hits:
        log("Renderizando {} ({:.1f}σ)...".format(a["symbol"], abs(a["sigma"])))
        add_hit(a)

    log("Pronto: {} card(s) em docs/social/".format(len(hits)))


if __name__ == "__main__":
    main()
