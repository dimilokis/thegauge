# -*- coding: utf-8 -*-
"""notify_telegram.py — avisa no Telegram pessoal (nao e canal de divulgacao,
e so pro Ygor) que os cards do dia estao prontos, com o link direto. Sem isso
seria preciso abrir o GitHub/Actions pra saber que rodou.

Usa as mesmas secrets TG_BOT_TOKEN/TG_CHAT_ID do alerta de sigma extremo em
gauge_live.py (README tem o passo a passo de como criar o bot). Se as
secrets nao existirem, sai calado — nao quebra o workflow.
"""
import os, sys, json
import requests

TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")


def main():
    if len(sys.argv) < 2:
        print("uso: notify_telegram.py <social_dir_url> [n_cards]")
        return
    url = sys.argv[1]
    n = sys.argv[2] if len(sys.argv) > 2 else "?"

    if not TG_TOKEN or not TG_CHAT:
        print("Telegram nao configurado — pulando aviso.")
        return

    text = "📊 Cards do dia prontos: {} moeda(s) em destaque.\n{}".format(n, url)
    try:
        r = requests.post(
            "https://api.telegram.org/bot{}/sendMessage".format(TG_TOKEN),
            data={"chat_id": TG_CHAT, "text": text},
            timeout=15,
        )
        print("Telegram: HTTP {}".format(r.status_code))
    except Exception as e:
        print("Falha ao notificar Telegram: {}".format(e))


if __name__ == "__main__":
    main()
