# -*- coding: utf-8 -*-
"""post_x.py — posta automaticamente 1x/dia no X (Twitter) o angulo mais forte
do snapshot real, sem intervencao manual. Roda dentro do GitHub Actions.

Idempotente: guarda a data do ultimo post em last_post.json (commitado de volta
pelo workflow) — se rodar 2x no mesmo dia (re-run manual), nao duplica, a nao
ser que --force seja passado.

Precisa das secrets: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
(gerados no X Developer Portal, App com permissao Read+Write, OAuth 1.0a).
"""
import os, sys, json, argparse
from datetime import datetime, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from angles import build_tweet
from localday import today as br_today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "docs", "gauge_live.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_post.json")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://thegauge.art")


def log(m):
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), m), flush=True)


def already_posted_today():
    try:
        s = json.load(open(STATE_PATH))
        return s.get("date") == br_today().isoformat()
    except Exception:
        return False


def save_state(angle, text):
    json.dump({"date": br_today().isoformat(), "angle": angle, "text": text},
               open(STATE_PATH, "w"), indent=2)


def post_to_x(text):
    import tweepy
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    resp = client.create_tweet(text=text)
    return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="posta mesmo se ja postou hoje")
    ap.add_argument("--dry-run", action="store_true", help="gera o texto mas nao posta")
    args = ap.parse_args()

    if not args.force and already_posted_today():
        log("Ja postou hoje — pulando (use --force pra postar de novo).")
        return

    if not os.path.exists(JSON_PATH):
        log("gauge_live.json nao encontrado ainda — pipeline de dado roda antes deste job."); sys.exit(1)

    snapshot = json.load(open(JSON_PATH, encoding="utf-8"))
    angle, text = build_tweet(snapshot, DASHBOARD_URL)
    if text is None:
        log("Nenhum angulo valido hoje — sem post."); return

    log("Angulo escolhido: {}".format(angle))
    log("Texto ({} chars):\n{}".format(len(text), text))

    if args.dry_run:
        log("(--dry-run, nao postou de verdade)")
        return

    resp = post_to_x(text)
    log("Postado! id={}".format(resp.data.get("id") if resp and resp.data else "?"))
    save_state(angle, text)


if __name__ == "__main__":
    main()
