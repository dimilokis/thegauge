# -*- coding: utf-8 -*-
"""angles.py — mesma logica do motor de marketing (escolhe o angulo mais forte
do dia a partir do snapshot real e gera o texto do tweet), adaptada pra rodar
sem clipboard dentro do GitHub Actions. Todo numero vem do JSON real."""
import itertools, random

from localday import today as br_today

SIGMA = "σ"


def verdict_word(v):
    return v


def pick_angles(d):
    A = [a for a in d["assets"] if not a["is_market"]]
    btc = next(a for a in d["assets"] if a["is_market"])
    angles = []

    hits = sorted([a for a in A if abs(a["sigma"]) >= 2.5 and a["from_btc_pct"] <= 40],
                  key=lambda a: -abs(a["sigma"]))
    if hits:
        angles.append(("anomaly", {"hits": hits, "n": d["universe_size"]}))

    best = None
    for x, y in itertools.combinations(A, 2):
        if abs(abs(x["ret_pct"]) - abs(y["ret_pct"])) < 0.5 and abs(x["ret_pct"]) >= 2.5:
            hi, lo = (x, y) if abs(x["sigma"]) > abs(y["sigma"]) else (y, x)
            gap = abs(hi["sigma"]) - abs(lo["sigma"])
            if abs(hi["sigma"]) >= 1.5 and abs(lo["sigma"]) <= 0.8 and (best is None or gap > best[0]):
                best = (gap, hi, lo)
    if best:
        angles.append(("contrast", {"hi": best[1], "lo": best[2]}))

    movers = sorted([a for a in A if abs(a["ret_pct"]) >= 3], key=lambda a: -abs(a["ret_pct"]))[:10]
    if abs(btc["ret_pct"]) >= 2 and len(movers) >= 5:
        tide = [a for a in movers if a["from_btc_pct"] > 60]
        if len(tide) >= max(3, len(movers) // 2):
            angles.append(("tide", {"btc": btc, "movers": movers, "tide": tide}))

    # ANGULO DE CARRY REMOVIDO DA ROTACAO (30/jul/2026, decisao do usuario).
    # Motivo: funding negativo em mercado com posicionamento vendido pesado e'
    # CONSEQUENCIA MECANICA, nao descoberta -- quem acompanha o mercado ja sabe.
    # Enquadrar como "most people think longs always pay" vendia o obvio como
    # insight. A funcao gen_carry fica no arquivo mas fora do GEN/WEIGHT.

    if not hits:
        angles.append(("quiet", {"n": d["universe_size"]}))

    return angles


def fit280(lines, url):
    while lines:
        txt = "\n".join(lines) + "\n" + url
        if len(txt) <= 280:
            return txt
        lines = lines[:-1]
    return url


def gen_anomaly(p, rng, url):
    hits = p["hits"]
    a = hits[0]
    times = abs(a["sigma"])
    hook = rng.choice([
        "{} moved {:.1f}{} today — {:.0f}x its normal daily swing — and Bitcoin explains {}% of it.".format(
            a["symbol"], abs(a["sigma"]), SIGMA, times, a["from_btc_pct"]),
        "Out of {} assets scanned, {} is the outlier: {:.1f}{} move, only {}% of it from Bitcoin.".format(
            p["n"], a["symbol"], abs(a["sigma"]), SIGMA, a["from_btc_pct"]),
    ])
    lines = [hook, "Whatever is happening, it's this coin's own story — not market tide."]
    for extra in hits[1:3]:
        lines.append("{}: {:.1f}{}, {} ({}% from BTC)".format(
            extra["symbol"], abs(extra["sigma"]), SIGMA, extra["verdict"].lower(), extra["from_btc_pct"]))
    return fit280(lines, "Live board, free: " + url)


def gen_contrast(p, rng, url):
    hi, lo = p["hi"], p["lo"]
    lines = [
        "{} {:+.1f}% and {} {:+.1f}% today. Basically the same size move.".format(
            hi["symbol"], hi["ret_pct"], lo["symbol"], lo["ret_pct"]),
        "For {} that's {:.1f}{} — a genuinely unusual day.".format(hi["symbol"], abs(hi["sigma"]), SIGMA),
        "For {} it's below its own average daily swing.".format(lo["symbol"]),
        "A % number without context will lie to you.",
    ]
    return fit280(lines, "Free live board: " + url)


def gen_tide(p, rng, url):
    btc, movers, tide = p["btc"], p["movers"], p["tide"]
    direction = "red" if btc["ret_pct"] < 0 else "green"
    lines = [
        "Everything's {} today — but look closer:".format(direction),
        "{} of the top {} movers are just following Bitcoin (60%+ of the move explained by BTC).".format(
            len(tide), len(movers)),
        "The coins didn't change. The tide did.",
    ]
    return fit280(lines, "See the split, free: " + url)


def gen_quiet(p, rng, url):
    n = p["n"]
    lines = rng.choice([
        ["{} assets scanned. Nothing statistically unusual today — every move within its coin's normal range.".format(n),
         "Days like this are where overtrading quietly eats accounts.",
         "Sometimes the edge is the chair."],
        ["Scanned {} assets: zero anomalies today. Every move is within normal range for its coin.".format(n),
         "No unusual volume, no independent breakouts, nothing.",
         "The honest read: there's nothing to do. That's information too."],
    ])
    return fit280(lines, url)


def gen_carry(p, rng, url):
    """Angulo do CUSTO DE CARREGAR -- o que nenhum outro screener mostra.

    Por que este angulo existe: praticamente todo mundo no varejo assume que
    'funding positivo, comprado paga' e a regra permanente do mercado. Em 2026
    isso INVERTEU: medido sobre 2,17M pagamentos (696 moedas, 2022-2026), a
    media e -2,96% a.a. e 17 dos ultimos 18 meses foram negativos. Ou seja: em
    boa parte do mercado hoje, quem esta comprado e PAGO pra estar.

    Todo numero abaixo sai do snapshot real -- regra da casa."""
    c = p["carry"]
    pay = p["pagam"]
    mes = c["reference_month"]
    # NAO citar o maior pagador isolado. Verificado em 30/jul/2026: HOME pagou
    # +116% de funding em junho -- e CAIU 62,8% no mesmo mes. Funding extremo e'
    # quase sempre COMPENSACAO por segurar um ativo em colapso, nao dinheiro
    # gratis. Citar so o numero grande seria tecnicamente verdadeiro e
    # substancialmente enganoso -- e o produto inteiro se apoia em nao fazer
    # isso. Lidera-se com a estatistica robusta (mediana/proporcao).
    if pay:
        lines = rng.choice([
            ["Most people think being long always costs you funding. In {} it didn't:".format(mes),
             "{}% of the {} perp-listed assets PAID longs to hold.".format(
                 c["share_paying_longs_pct"], c["coins_with_perp"]),
             "Usually that's compensation for holding something falling — not free money.",
             "Every screener shows the signal. None show what holding it costs."],
            ["The cost of holding is the number nobody shows you.",
             "{} of {} perp assets paid longs in {} — median {:+.2f}% for the month.".format(
                 int(round(c["share_paying_longs_pct"] * c["coins_with_perp"] / 100)),
                 c["coins_with_perp"], mes, c["median_hold_cost_pct"]),
             "Measured payments, not an annualized projection.",
             "High funding is a warning label, not a yield."],
        ])
    else:
        lines = ["In {}, the median perp asset charged longs {:+.2f}% to hold.".format(
            mes, c["median_hold_cost_pct"]),
            "Small number. It still compounds against every position you leave open.",
            "The signal is free. The holding isn't."]
    return fit280(lines, url)


GEN = {"anomaly": gen_anomaly, "contrast": gen_contrast, "tide": gen_tide, "quiet": gen_quiet}
WEIGHT = {"anomaly": 3, "contrast": 2, "tide": 2, "quiet": 1}


def build_tweet(snapshot, url, seed=None):
    """Retorna (angulo, texto_tweet) ou (None, None) se nao houver angulo valido."""
    angles = pick_angles(snapshot)
    if not angles:
        return None, None
    rng = random.Random(seed if seed is not None else br_today().toordinal())
    names = [a[0] for a in angles]
    weights = [WEIGHT[n] for n in names]
    name, payload = angles[rng.choices(range(len(angles)), weights=weights)[0]]
    text = GEN[name](payload, rng, url)
    return name, text
