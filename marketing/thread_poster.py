# -*- coding: utf-8 -*-
"""thread_poster.py — posta cada card do dia como reply na MESMA thread do X,
na hora que o card aparece (chamado por process_alerts() em gauge_live.py,
logo depois de social_kit.add_hit() e do alerta do Telegram). Sem horario
fixo, sem 1-post-por-dia: a thread cresce conforme os ativos entram em
estado extremo, do jeito que o card do dia ja acumula em docs/social/.

Custo (pay-per-use X API desde 6/fev/2026): $0.015/post sem link, $0.20/post
com link. So o PRIMEIRO tweet do dia (a raiz da thread) leva link -- uma vez
so, ali quem ve a thread ja sabe onde clicar. As replies seguintes (cada
card novo) NAO levam link. Pior caso realista (MAX_DAY_CARDS=12 cards num
dia caotico): $0.20 + 11*$0.015 ~= $0.365 naquele dia.

Nao configurado (faltam as 4 secrets) ou X_THREAD_DRY_RUN=1 -> so loga e
sai, mesmo padrao do send_telegram() em gauge_live.py: nunca derruba o
resto do pipeline por causa disso.
"""
import os, json
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "thread_state.json")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://thegauge.art")
SIGMA = "σ"

ENV_VARS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


def log(msg):
    print("[{}] thread_poster: {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def _configured():
    return all(os.environ.get(v) for v in ENV_VARS)


def _load_state():
    today = date.today().isoformat()
    try:
        s = json.load(open(STATE_PATH, encoding="utf-8"))
        if s.get("date") == today:
            return s
    except Exception:
        pass
    return {"date": today, "root_id": None, "last_id": None, "posted": []}


def _save_state(s):
    json.dump(s, open(STATE_PATH, "w", encoding="utf-8"), indent=1)


def _card_caption(asset):
    return "{} — {:.1f}{} move, only {}% explained by BTC. {}.".format(
        asset["symbol"], abs(asset["sigma"]), SIGMA, asset["from_btc_pct"], asset["verdict"])


def _clients():
    import tweepy
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
    api_v1 = tweepy.API(auth)  # so pra upload de midia -- v2 nao tem endpoint pra isso
    client_v2 = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"], consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"], access_token_secret=os.environ["X_ACCESS_SECRET"])
    return api_v1, client_v2


def post_card_to_thread(asset, png_path):
    """Chamado uma vez por ativo que ACABOU de entrar em estado extremo.
    Cria a thread do dia se ainda nao existe (1o card = raiz, com link);
    caso contrario, responde ao ultimo tweet da thread (sem link)."""
    if os.environ.get("X_THREAD_DRY_RUN") == "1":
        log("dry-run: postaria {} card na thread de hoje.".format(asset["symbol"]))
        return
    if not _configured():
        log("X nao configurado (faltam as 4 secrets) — pulando post.")
        return

    state = _load_state()
    if asset["symbol"] in state["posted"]:
        log("{} ja foi postado na thread de hoje — pulando (evita duplicata em re-run).".format(asset["symbol"]))
        return

    try:
        api_v1, client_v2 = _clients()
        media = api_v1.media_upload(filename=png_path)

        if state["root_id"] is None:
            text = ("Today's outliers on The Gauge — cards post live as they cross the "
                     "threshold, not on a fixed schedule.\n\n" + DASHBOARD_URL + "/social.html\n\n"
                     + _card_caption(asset))
            resp = client_v2.create_tweet(text=text, media_ids=[media.media_id_string])
            new_id = resp.data["id"]
            state["root_id"] = new_id
            log("thread do dia criada, raiz={}".format(new_id))
        else:
            resp = client_v2.create_tweet(text=_card_caption(asset), media_ids=[media.media_id_string],
                                          in_reply_to_tweet_id=state["last_id"])
            new_id = resp.data["id"]
            log("card de {} postado como reply em {}".format(asset["symbol"], state["last_id"]))

        state["last_id"] = new_id
        state["posted"].append(asset["symbol"])
        _save_state(state)
    except Exception as e:
        log("falha ao postar {} na thread: {}".format(asset["symbol"], e))
