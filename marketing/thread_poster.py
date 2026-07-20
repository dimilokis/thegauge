# -*- coding: utf-8 -*-
"""thread_poster.py — posta cada card do dia como reply na MESMA thread do X,
na hora que o card aparece (chamado por process_alerts() em gauge_live.py,
logo depois de social_kit.add_hit() e do alerta do Telegram). Sem horario
fixo, sem 1-post-por-dia: a thread cresce conforme os ativos entram em
estado extremo, do jeito que o card do dia ja acumula em docs/social/.

ZERO link em qualquer post, sempre -- nem a raiz da thread leva link (era
assim antes, tirado 20/jul). Custo pay-per-use (desde 6/fev/2026): $0.015
por post SEM link, $0.20 COM link -- 13x mais caro, por isso nunca. Pior
caso realista (MAX_DAY_CARDS=12 + 1 post de abertura): 13*$0.015 ~= $0.20
naquele dia; a maioria dos dias custa uma fracao disso.

Estrutura do dia: o 1o card do dia primeiro dispara um tweet de ABERTURA
(sem imagem, so o gancho + hashtags genericas) -- e so DEPOIS o card em si
entra como reply nesse tweet. Ou seja, a raiz nunca "engole" o primeiro
card; todo card, incluindo o primeiro, sempre vira uma reply com imagem.

Nao configurado (faltam as 4 secrets) ou X_THREAD_DRY_RUN=1 -> so loga e
sai, mesmo padrao do send_telegram() em gauge_live.py: nunca derruba o
resto do pipeline por causa disso.
"""
import os, json
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "thread_state.json")
SIGMA = "σ"
POINT_DOWN = "\U0001F447"  # 👇

ENV_VARS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")

INTRO_TEXTS = [
    "Today's outliers on The Gauge {}\n\nAssets moving statistically extreme today — "
    "and independent of Bitcoin, not just riding its wave.\n\n#crypto #Bitcoin".format(POINT_DOWN),
    "What stood out today {}\n\nEach one below moved in a way that's unusual for itself, "
    "not just because the whole market moved.\n\n#crypto #Bitcoin".format(POINT_DOWN),
]


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


def _hashtags(symbol):
    return "#{} #crypto #Bitcoin".format(symbol)


def _card_caption(asset):
    return "{} — {:.1f}{} move, only {}% explained by BTC. {}.\n\n{}".format(
        asset["symbol"], abs(asset["sigma"]), SIGMA, asset["from_btc_pct"], asset["verdict"],
        _hashtags(asset["symbol"]))


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
    1o card do dia: cria o tweet de abertura (sem imagem, sem link) e DEPOIS
    posta o card como reply dele. Cards seguintes: reply direto no ultimo
    tweet da thread. Nenhum post, em nenhum momento, leva link."""
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

        if state["root_id"] is None:
            import random
            intro = random.Random(date.today().toordinal()).choice(INTRO_TEXTS)
            resp = client_v2.create_tweet(text=intro)
            state["root_id"] = resp.data["id"]
            state["last_id"] = state["root_id"]
            log("thread do dia aberta, raiz={}".format(state["root_id"]))

        media = api_v1.media_upload(filename=png_path)
        resp = client_v2.create_tweet(text=_card_caption(asset), media_ids=[media.media_id_string],
                                      in_reply_to_tweet_id=state["last_id"])
        new_id = resp.data["id"]
        log("card de {} postado como reply em {}".format(asset["symbol"], state["last_id"]))

        state["last_id"] = new_id
        state["posted"].append(asset["symbol"])
        _save_state(state)
    except Exception as e:
        log("falha ao postar {} na thread: {}".format(asset["symbol"], e))
