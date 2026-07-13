# -*- coding: utf-8 -*-
"""render_cards.py — gera as imagens do post diario (1 card por moeda em
destaque + um arquivo de texto pra thread), na mesma paleta/tipografia do
dashboard (docs/index.html). Roda dentro do GitHub Actions 1x/dia; publica em
docs/social/<data>/ que o Cloudflare ja serve automaticamente em
thegauge.art/social/<data>/ — o usuario abre esse link do celular, sem
precisar estar no PC nem ter o repo aberto.

Reaproveita a escolha de angulo do daily_post.py (mesma logica, mesmo dado
real). So gera cards pro angulo ANOMALY (e' o unico que tem "uma moeda por
card" fazendo sentido — os outros geram 1 imagem so, ainda nao implementada
aqui por escopo).
"""
import json, os, sys, io, textwrap, urllib.request
from datetime import date, datetime, timezone

from PIL import Image, ImageDraw, ImageFont, ImageOps

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
GAUGE_ROOT = os.path.dirname(ROOT)
JSON_PATH = os.path.join(GAUGE_ROOT, "docs", "gauge_live.json")
FONTS = os.path.join(ROOT, "fonts")
OUT_ROOT = os.path.join(GAUGE_ROOT, "docs", "social")
DASHBOARD_URL = "https://thegauge.art"
MAX_CARDS = 5
SIGMA = "σ"

SIZE = 1080
BG = "#080808"
SURFACE = "#0f0f0f"
BORDER = "#1f1f1f"
BORDER2 = "#2a2a2a"
TEXT = "#e8e4dc"
MUTED = "#8a8680"
DIM = "#4a4640"
GOLD = "#c9a96e"
ICE = "#7eb8c9"
HEAT = "#c97a6e"
GREEN = "#7ec998"

VERDICT_COLOR = {"Oversold": ICE, "Overbought": HEAT, "Strong Uptrend": GREEN, "Neutral": GOLD}

UA = {"User-Agent": "Mozilla/5.0"}


def log(msg):
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def font(path, size, weight=None, italic=False):
    """path: 'serif' (Cormorant Garamond, so tem eixo Weight) ou 'sans' (Inter,
    tem eixo Optical size + Weight, NESSA ordem — passar so 1 valor faz o
    Pillow setar o eixo errado, todo texto saia sempre no peso default)."""
    name = ("CormorantGaramond-Italic.ttf" if italic else
            "CormorantGaramond.ttf" if path == "serif" else "Inter.ttf")
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    try:
        axes = f.get_variation_axes()
        if axes:
            values = []
            for ax in axes:
                axname = ax["name"].decode() if isinstance(ax["name"], bytes) else ax["name"]
                if axname == "Weight" and weight:
                    values.append(weight)
                elif axname.lower().startswith("optical"):
                    values.append(max(ax["minimum"], min(ax["maximum"], size / 8)))
                else:
                    values.append(ax["default"])
            f.set_variation_by_axes(values)
    except Exception:
        pass
    return f


def text_h(d, txt, f):
    b = d.textbbox((0, 0), txt, font=f)
    return b[3] - b[1], b[1]  # altura real, offset do topo


def truncate(d, txt, f, max_w):
    if d.textlength(txt, font=f) <= max_w:
        return txt
    while txt and d.textlength(txt + "…", font=f) > max_w:
        txt = txt[:-1]
    return txt + "…"


def fetch_icon(url, px):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=10) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGBA")
        im = ImageOps.fit(im, (px, px), Image.LANCZOS)
        mask = Image.new("L", (px, px), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, px, px], fill=255)
        out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        return out
    except Exception as e:
        log("  icone falhou ({}) — usando fallback letra.".format(e))
        return None


def icon_fallback(letter, px, color):
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, px, px], fill=hx(SURFACE), outline=hx(BORDER2), width=2)
    f = font("sans", int(px * 0.42), weight=500)
    bbox = d.textbbox((0, 0), letter, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((px / 2 - w / 2 - bbox[0], px / 2 - h / 2 - bbox[1]), letter, font=f, fill=hx(color))
    return im


def fmt_price(p):
    if p >= 1:
        return "${:,.2f}".format(p)
    if p >= 0.01:
        return "${:.4f}".format(p)
    return "${:.8f}".format(p).rstrip("0")


def draw_score_bar(d, x, y, w, h, score, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=hx(BORDER))
    fill_w = max(h, w * max(0, min(100, score)) / 100)
    d.rounded_rectangle([x, y, x + fill_w, y + h], radius=h / 2, fill=hx(color))


def render_card(asset, out_path):
    img = Image.new("RGB", (SIZE, SIZE), hx(BG))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, SIZE - 1, SIZE - 1], outline=hx(BORDER), width=2)

    verdict = asset["verdict"]
    # Neutral com retorno grande: colore pela direcao do preco, nao fica neutro cinza --
    # senao um +31% "Neutral" (score no meio da regua) parece sem graca na imagem.
    color = VERDICT_COLOR.get(verdict, GOLD)
    if verdict == "Neutral" and abs(asset["ret_pct"]) >= 5:
        color = GREEN if asset["ret_pct"] > 0 else HEAT

    pad = 72
    # eyebrow
    f_eyebrow = font("sans", 26, weight=500)
    d.text((pad, 64), "THE GAUGE  ·  DAILY OUTLIER", font=f_eyebrow, fill=hx(GOLD))

    # icone + nome
    icon_px = 132
    icon = fetch_icon(asset["icon"], icon_px) if asset.get("icon") else None
    if icon is None:
        icon = icon_fallback(asset["symbol"][0], icon_px, GOLD)
    img.paste(icon, (pad, 150), icon)

    text_x = pad + icon_px + 32
    max_w = SIZE - pad - text_x
    f_symbol = font("serif", 96, weight=500)
    f_name = font("sans", 34, weight=400)
    d.text((text_x, 150), truncate(d, asset["symbol"], f_symbol, max_w), font=f_symbol, fill=hx(TEXT))
    name = asset.get("name") or asset["symbol"]
    d.text((text_x + 2, 260), truncate(d, name, f_name, max_w), font=f_name, fill=hx(MUTED))

    # numero hero + sigma. Sans (Inter), nao serif — Cormorant Garamond nao
    # tem glifo de sigma nesse eixo variavel (renderiza um tofu "NO GLYPH").
    # O "σ" sai MENOR, cor mais fraca (MUTED) e com respiro do numero --
    # mesma cor/tamanho do numero fazia ele ler como um "0" deformado colado
    # no numero (achado do usuario 13/jul).
    cursor = 400
    f_hero = font("sans", 200, weight=800)
    num = "{:.1f}".format(abs(asset["sigma"]))
    h, off = text_h(d, num, f_hero)
    d.text((pad, cursor - off), num, font=f_hero, fill=hx(color))
    num_w = d.textlength(num, font=f_hero)

    f_unit = font("sans", 96, weight=600)
    unit_x = pad + num_w + 20
    uh, uoff = text_h(d, SIGMA, f_unit)
    # alinha pela base (bottom) do numero, nao pelo topo -- sigma "sentado"
    # do lado do numero, como uma unidade (kg, %, etc), nao continuando ele.
    num_bottom = cursor - off + h
    d.text((unit_x, num_bottom - uh - uoff), SIGMA, font=f_unit, fill=hx(MUTED))
    cursor += h + 28

    f_sub = font("sans", 32, weight=400)
    sub = "{:.0f}x its normal daily swing · {}% explained by Bitcoin".format(
        abs(asset["sigma"]), asset["from_btc_pct"])
    h, off = text_h(d, sub, f_sub)
    d.text((pad, cursor - off), sub, font=f_sub, fill=hx(MUTED))
    cursor += h + 40

    # verdict badge
    f_badge = font("sans", 30, weight=600)
    bbox = d.textbbox((0, 0), verdict.upper(), font=f_badge)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bx0, by0 = pad, cursor
    d.rounded_rectangle([bx0, by0, bx0 + bw + 48, by0 + bh + 32], radius=6, outline=hx(color), width=2)
    d.text((bx0 + 24 - bbox[0], by0 + 16 - bbox[1]), verdict.upper(), font=f_badge, fill=hx(color))
    cursor = by0 + bh + 32 + 56

    # stats row: score bar, tier, preco/retorno
    y_stats = cursor
    f_label = font("sans", 24, weight=500)
    f_value = font("sans", 40, weight=600)

    d.text((pad, y_stats), "GAUGE SCORE", font=f_label, fill=hx(DIM))
    draw_score_bar(d, pad, y_stats + 36, 340, 14, asset["score"], color)
    d.text((pad, y_stats + 60), "{:.0f} / 100".format(asset["score"]), font=f_value, fill=hx(TEXT))

    col2_x = pad + 400
    d.text((col2_x, y_stats), "LIQUIDITY TIER", font=f_label, fill=hx(DIM))
    d.text((col2_x, y_stats + 60), "Tier {}".format(asset["tier"]), font=f_value, fill=hx(TEXT))

    col3_x = pad + 620
    d.text((col3_x, y_stats), "24H", font=f_label, fill=hx(DIM))
    ret_color = GREEN if asset["ret_pct"] >= 0 else HEAT
    d.text((col3_x, y_stats + 60), "{:+.1f}%".format(asset["ret_pct"]), font=f_value, fill=hx(ret_color))

    # rodape
    f_foot = font("sans", 28, weight=400)
    d.line([pad, SIZE - 120, SIZE - pad, SIZE - 120], fill=hx(BORDER), width=1)
    d.text((pad, SIZE - 92), "{}   ·   {}".format(fmt_price(asset["price"]), DASHBOARD_URL),
            font=f_foot, fill=hx(MUTED))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    f_ts = font("sans", 24, weight=400)
    bbox = d.textbbox((0, 0), ts, font=f_ts)
    d.text((SIZE - pad - (bbox[2] - bbox[0]), SIZE - 92), ts, font=f_ts, fill=hx(DIM))

    img.save(out_path)


def build_thread_text(hits, out_path):
    lines = []
    n = len(hits)
    lines.append("[1/{}] {} coins scanned. {} stand out today — statistically extreme moves, "
                 "independent of Bitcoin. Thread with the breakdown of each 👇".format(
                     n + 1, "100", n))
    lines.append("#crypto #Bitcoin #altcoins")
    lines.append("")
    for i, a in enumerate(hits, start=2):
        lines.append("[{}/{}] {} — {:.1f}σ move, only {}% explained by BTC. {}.".format(
            i, n + 1, a["symbol"], abs(a["sigma"]), a["from_btc_pct"], a["verdict"]))
        lines.append("(attach: {}.png)".format(a["symbol"]))
        lines.append("")
    lines.append("Free live dashboard, updated hourly: {}".format(DASHBOARD_URL))
    lines.append("#{}".format(" #".join(a["symbol"] for a in hits)))
    open(out_path, "w", encoding="utf-8").write("\n".join(lines))


def main():
    d = json.load(open(JSON_PATH, encoding="utf-8"))
    A = [a for a in d["assets"] if not a["is_market"]]
    hits = sorted([a for a in A if abs(a["sigma"]) >= 2.5 and a["from_btc_pct"] <= 40],
                  key=lambda a: -abs(a["sigma"]))[:MAX_CARDS]

    if not hits:
        log("Nenhum outlier hoje — nao ha cards pra gerar (dia 'quiet').")
        return

    out_dir = os.path.join(OUT_ROOT, date.today().isoformat())
    os.makedirs(out_dir, exist_ok=True)

    for a in hits:
        path = os.path.join(out_dir, "{}.png".format(a["symbol"]))
        log("Renderizando {} ({:.1f}σ)...".format(a["symbol"], abs(a["sigma"])))
        render_card(a, path)

    build_thread_text(hits, os.path.join(out_dir, "post.txt"))

    # manifest: a pasta em si nao e navegavel (hosting estatico nao lista
    # diretorio — dava 404 tentando abrir /social/ direto, achado do usuario
    # 13/jul). docs/social.html le este JSON pra montar uma pagina de verdade.
    manifest = {
        "date": date.today().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets": [{"symbol": a["symbol"], "name": a.get("name"), "sigma": a["sigma"],
                    "verdict": a["verdict"], "file": "{}.png".format(a["symbol"])} for a in hits],
    }
    json.dump(manifest, open(os.path.join(OUT_ROOT, "latest.json"), "w"), indent=1)

    log("Pronto: {} cards + post.txt em {}".format(len(hits), out_dir))
    log("Publico em: {}/social.html".format(DASHBOARD_URL))


if __name__ == "__main__":
    main()
