# -*- coding: utf-8 -*-
"""Gera a imagem do tweet fixado -- explica o produto pra quem chega pelos
posts automaticos (que agora nao levam link nenhum). 1600x900 (16:9, o
formato que a X mostra maior no timeline)."""
import math
from PIL import Image, ImageDraw, ImageFont

FDIR = "C:/Windows/Fonts/"
W, H = 1600, 900
BG = (8, 8, 8)
GOLD = (201, 169, 110)
GOLD_DIM = (96, 82, 56)
TEXT = (232, 228, 220)
MUTED = (120, 114, 106)
DIM = (58, 54, 50)


def F(name, size):
    return ImageFont.truetype(FDIR + name, int(size))


def tracked(d, text, font, x, y, fill, tracking=0.0, anchor_left=True, cx=None):
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    start = x if anchor_left else (cx - total / 2 if cx is not None else x)
    for ch, w in zip(text, widths):
        d.text((start, y), ch, font=font, fill=fill)
        start += w + tracking
    return total


def gauge_mark(d, cx, cy, r):
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=125, end=55, fill=GOLD, width=5)
    ang = math.radians(-58)
    nx, ny = cx + r * 0.62 * math.cos(ang), cy + r * 0.62 * math.sin(ang)
    d.line([(cx, cy), (nx, ny)], fill=TEXT, width=4)
    pr = 5
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=GOLD)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

L = 90  # margem esquerda do bloco de titulo

# eyebrow
tracked(d, "FREE  ·  NO SIGNUP  ·  UPDATES LIVE", F("segoeuib.ttf", 22), L, 96, GOLD, 3)

# THE / GAUGE
f_title = F("georgiab.ttf", 110)
tracked(d, "THE", f_title, L, 148, TEXT, 3)
tracked(d, "GAUGE", f_title, L, 258, GOLD, 3)

# tagline
d.text((L, 400), "Read any coin in five seconds.", font=F("georgiai.ttf", 34), fill=MUTED)

# rule
d.line([(L, 470), (L + 430, 470)], fill=GOLD_DIM, width=2)

# mark + wordmark url, bottom-left
gauge_mark(d, L + 20, 780, 22)
d.text((L + 56, 762), "thegauge.art", font=F("georgia.ttf", 30), fill=TEXT)

# ---- right column: the three reads ----
RX = 900
rows = [
    ("SCORE", "0–100 — where a coin sits in its own 90-day range, not the market's."),
    ("MOVE", "Measured in standard deviations against that coin's own history, "
             "so a scary % isn't always a big deal."),
    ("DRIVER", "How much of the move is Bitcoin's tide vs. the coin acting on its own."),
]
ry = 150
for label, desc in rows:
    tracked(d, label, F("segoeuib.ttf", 26), RX, ry, GOLD, 2)
    ry += 44
    # wrap desc manually at ~46 chars
    import textwrap
    for line in textwrap.wrap(desc, width=46):
        d.text((RX, ry), line, font=F("georgia.ttf", 27), fill=TEXT)
        ry += 38
    ry += 46

img.save("docs/pinned-tweet.png", quality=95)
print("saved: docs/pinned-tweet.png", img.size)
