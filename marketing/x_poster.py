# -*- coding: utf-8 -*-
"""x_poster.py — posta cada card do dia como tweet INDEPENDENTE (chamado por
gauge_live.py assim que um ativo entra em estado extremo, na hora, sem post
1x/dia). Sem link em nenhum post, sempre.

Mudanca de 21/jul: era 1 tweet de abertura (raiz, sem imagem) + cada card
como REPLY nessa mesma thread. Visualizacao real mostrou que a raiz pega
views normais mas TODAS as replies (= todos os cards, a informacao de
verdade) ficam com views perto de zero — bate com o que a propria X
documenta: replies tem distribuicao algoritmica muito menor que posts
originais (nao entram no For You, so aparecem pra quem abre a conversa).
Cada card agora e' seu proprio tweet raiz, competindo igual pela
distribuicao normal de post original — e sem o tweet de abertura extra,
custa uma fracao a menos por dia.

Custo pay-per-use (desde 6/fev/2026): todo card leva imagem = fluxo
multi-chamada de upload, medido em ~$0.03/post na conta real (nao os
$0.015 nominal de post so-texto sem midia).

Nao configurado (faltam as 4 secrets) ou X_THREAD_DRY_RUN=1 -> so loga e
sai, mesmo padrao do send_telegram() em gauge_live.py: nunca derruba o
resto do pipeline por causa disso."""
import os, json
from datetime import datetime, timezone

from localday import today as br_today

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "thread_state.json")
SIGMA = "σ"

ENV_VARS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


def log(msg):
    print("[{}] x_poster: {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def _configured():
    return all(os.environ.get(v) for v in ENV_VARS)


def _load_state():
    """Estado so precisa evitar duplicata (re-run do mesmo dia) -- nao ha
    mais raiz/thread pra amarrar."""
    today = br_today().isoformat()
    try:
        s = json.load(open(STATE_PATH, encoding="utf-8"))
        if s.get("date") == today:
            return s
    except Exception:
        pass
    return {"date": today, "posted": []}


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


def post_card(asset, png_path):
    """Chamado uma vez por ativo que ACABOU de entrar em estado extremo.
    Tweet independente, com imagem, sem link, sem reply em nada."""
    if os.environ.get("X_THREAD_DRY_RUN") == "1":
        log("dry-run: postaria {} como tweet independente.".format(asset["symbol"]))
        return
    if not _configured():
        log("X nao configurado (faltam as 4 secrets) — pulando post.")
        return

    state = _load_state()
    if asset["symbol"] in state["posted"]:
        log("{} ja foi postado hoje — pulando (evita duplicata em re-run).".format(asset["symbol"]))
        return

    try:
        api_v1, client_v2 = _clients()
        media = api_v1.media_upload(filename=png_path)
        resp = client_v2.create_tweet(text=_card_caption(asset), media_ids=[media.media_id_string])
        log("{} postado como tweet independente ({})".format(asset["symbol"], resp.data["id"]))
        state["posted"].append(asset["symbol"])
        _save_state(state)
    except Exception as e:
        log("falha ao postar {}: {}".format(asset["symbol"], e))
