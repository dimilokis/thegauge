# -*- coding: utf-8 -*-
"""social_kit.py — acumula os cards do dia conforme os ativos vao entrando em
estado extremo (chamado por gauge_live.py a cada run, nao 1x/dia num horario
fixo). Cada chamada de add_hit() renderiza/atualiza o card daquele ativo e
reescreve o manifest com TUDO que ja apareceu hoje.

Antes disso era um batch unico as 13:20 UTC, fotografando so quem estava
extremo naquele minuto exato — uma moeda que disparasse as 15h e sumisse as
16h nunca virava card. Isso aqui acumula ao longo do dia inteiro.

A legenda de cada card e' gerada NO NAVEGADOR (docs/social.html), direto dos
campos deste manifest — nao existe mais post.txt com thread numerada: o
usuario posta cada card como imagem+texto avulsos (copy image / copy text),
nao como thread."""
import os, json
from datetime import datetime, timezone

from card_render import render_card
from localday import today as br_today

GAUGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(GAUGE_ROOT, "docs", "social")
MAX_DAY_CARDS = 12  # rede de seguranca p/ um dia caotico nao virar uma thread infinita


def _manifest_path():
    return os.path.join(OUT_ROOT, "latest.json")


def _load_today_manifest():
    today = br_today().isoformat()
    try:
        m = json.load(open(_manifest_path(), encoding="utf-8"))
        if m.get("date") == today:
            return m
    except Exception:
        pass
    return {"date": today, "generated_at": None, "assets": []}


def add_hit(asset):
    """Renderiza o card do asset e atualiza o kit social do dia (acumula,
    nao sobrescreve os outros ativos que ja entraram hoje). Devolve o path
    do PNG gerado, pra quem chamou (ex.: alerta do Telegram) poder anexar."""
    today = br_today().isoformat()
    out_dir = os.path.join(OUT_ROOT, today)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "{}.png".format(asset["symbol"]))
    render_card(asset, png_path)

    manifest = _load_today_manifest()
    manifest["assets"] = [a for a in manifest["assets"] if a["symbol"] != asset["symbol"]]
    manifest["assets"].append({
        "symbol": asset["symbol"], "name": asset.get("name"), "sigma": asset["sigma"],
        "from_btc_pct": asset["from_btc_pct"], "verdict": asset["verdict"],
        "file": "{}.png".format(asset["symbol"]),
    })
    manifest["assets"].sort(key=lambda a: -abs(a["sigma"]))
    manifest["assets"] = manifest["assets"][:MAX_DAY_CARDS]
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    json.dump(manifest, open(_manifest_path(), "w"), indent=1)
    return png_path
