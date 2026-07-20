# -*- coding: utf-8 -*-
"""Gera as imagens da thread fixada: 1 abertura + 3 conceitos (Score/Move/
Driver, espelhando a secao 'Four reads' da landing) + 1 fechamento com o
link. Verticais (1080x1350, 4:5) -- ocupam muito mais altura no timeline
do X do que a 16:9 anterior, texto grande o suficiente pra ler sem clicar."""
import textwrap
from PIL import Image, ImageDraw, ImageFont
import math

FDIR = "C:/Windows/Fonts/"
W, H = 1080, 1350
BG = (8, 8, 8)
GOLD = (201, 169, 110)
GOLD_DIM = (96, 82, 56)
TEXT = (232, 228, 220)
MUTED = (130, 124, 116)
ICE = (126, 184, 201)
HEAT = (201, 122, 110)
GREEN = (126, 201, 152)


def F(name, size):
    return ImageFont.truetype(FDIR + name, int(size))


def tracked(d, text, font, cx, y, fill, tracking=0.0):
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + tracking
    return total


def wrapped(d, text, font, cx, y, fill, width_chars, line_h, align="center"):
    for line in textwrap.wrap(text, width=width_chars):
        w = d.textlength(line, font=font)
        x = cx - w / 2 if align == "center" else cx
        d.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


def gauge_mark(d, cx, cy, r):
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=125, end=55, fill=GOLD, width=6)
    ang = math.radians(-58)
    nx, ny = cx + r * 0.62 * math.cos(ang), cy + r * 0.62 * math.sin(ang)
    d.line([(cx, cy), (nx, ny)], fill=TEXT, width=5)
    pr = 6
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=GOLD)


def base():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def eyebrow(d, text):
    tracked(d, text, F("segoeuib.ttf", 26), W / 2, 110, GOLD, 3)


def cx():
    return W // 2


# ---------------- 1. abertura ----------------
img, d = base()
eyebrow(d, "FREE  ·  NO SIGNUP  ·  UPDATES LIVE")
f_t = F("georgiab.ttf", 108)
tracked(d, "THE", f_t, cx(), 300, TEXT, 3)
tracked(d, "GAUGE", f_t, cx(), 415, GOLD, 3)
d.line([(cx() - 160, 590), (cx() + 160, 590)], fill=GOLD_DIM, width=2)
wrapped(d, "Read any coin in five seconds.", F("georgiai.ttf", 40), cx(), 630, MUTED, 30, 52)
gauge_mark(d, cx(), 1180, 34)
img.save("docs/pin1-intro.png", quality=95)

# ---------------- 2. score ----------------
img, d = base()
eyebrow(d, "I  ·  THE GAUGE SCORE")
wrapped(d, "Am I early — or am I late?", F("georgiab.ttf", 62), cx(), 220, TEXT, 15, 76)
wrapped(d, "0-100, built from where a coin sits in its own "
           "90-day range, its momentum, and distance from trend.",
        F("georgia.ttf", 34), cx(), 460, MUTED, 34, 48)
# mini viz: barra de score
by = 780
d.text((cx() - 260, by - 50), "18", font=F("georgiab.ttf", 56), fill=ICE)
d.rectangle([cx() - 160, by, cx() + 260, by + 10], fill=(40, 38, 34))
d.rectangle([cx() - 160, by, cx() - 160 + 420 * 0.18, by + 10], fill=ICE)
d.text((cx() - 160, by + 40), "cheap by its own history", font=F("georgiai.ttf", 28), fill=MUTED)
gauge_mark(d, cx(), 1220, 28)
img.save("docs/pin2-score.png", quality=95)

# ---------------- 3. move ----------------
img, d = base()
eyebrow(d, "II  ·  THE MOVE")
wrapped(d, "Is this real, or just a Tuesday?", F("georgiab.ttf", 58), cx(), 220, TEXT, 17, 74)
wrapped(d, "Today's move vs. how that specific coin usually "
           "behaves — in standard deviations, not raw percent.",
        F("georgia.ttf", 34), cx(), 450, MUTED, 34, 48)
by = 780
tag = "EXTREME · 3.1σ"
f_tag = F("segoeuib.ttf", 30)
tw = d.textlength(tag, font=f_tag)
pad = 26
d.rectangle([cx() - tw / 2 - pad, by, cx() + tw / 2 + pad, by + 66], outline=HEAT, width=2)
d.text((cx() - tw / 2, by + 16), tag, font=f_tag, fill=HEAT)
d.text((cx(), by + 100), "a candle that looks scary but is routine —", font=F("georgiai.ttf", 26), fill=MUTED, anchor="mt")
d.text((cx(), by + 136), "doesn't trick you into selling.", font=F("georgiai.ttf", 26), fill=MUTED, anchor="mt")
gauge_mark(d, cx(), 1220, 28)
img.save("docs/pin3-move.png", quality=95)

# ---------------- 4. driver ----------------
img, d = base()
eyebrow(d, "III  ·  THE DRIVER")
wrapped(d, "Is it the coin — or just Bitcoin?", F("georgiab.ttf", 58), cx(), 220, TEXT, 17, 74)
wrapped(d, "Every move is split: how much Bitcoin explains, "
           "how much is the coin acting on its own.",
        F("georgia.ttf", 34), cx(), 450, MUTED, 34, 48)
by = 780
d.text((cx(), by), "Independent", font=F("georgiab.ttf", 46), fill=GOLD, anchor="mt")
d.text((cx(), by + 66), "only 22% explained by BTC", font=F("georgia.ttf", 30), fill=MUTED, anchor="mt")
gauge_mark(d, cx(), 1220, 28)
img.save("docs/pin4-driver.png", quality=95)

# ---------------- 5. fechamento ----------------
img, d = base()
eyebrow(d, "FREE  ·  LIVE  ·  NO SIGNUP")
wrapped(d, "No signals. No hype.", F("georgiab.ttf", 64), cx(), 340, TEXT, 15, 80)
wrapped(d, "Just the numbers, updating every 15 minutes.", F("georgiai.ttf", 34), cx(), 500, MUTED, 32, 48)
d.line([(cx() - 160, 640), (cx() + 160, 640)], fill=GOLD_DIM, width=2)
tracked(d, "thegauge.art", F("georgiab.ttf", 64), cx(), 700, GOLD, 2)
gauge_mark(d, cx(), 1220, 34)
img.save("docs/pin5-cta.png", quality=95)

print("5 imagens geradas em docs/pin1..5-*.png")
