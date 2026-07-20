# -*- coding: utf-8 -*-
"""Foto de perfil do X a partir do MESMO glifo do favicon.svg (velocimetro),
escala 12.5x (64->800px), com margem de seguranca pro corte circular que o
X aplica em cima de qualquer imagem de perfil."""
from PIL import Image, ImageDraw

S = 800
BG = (8, 8, 8)
BORDER = (42, 42, 42)
GOLD = (201, 169, 110)
CREAM = (232, 228, 220)

img = Image.new("RGB", (S, S), BG)
d = ImageDraw.Draw(img)

k = S / 64.0
d.rounded_rectangle([0.5 * k, 0.5 * k, 63.5 * k, 63.5 * k], radius=13.5 * k, outline=BORDER, width=max(1, int(1 * k)))

cx, cy, r = 32 * k, 32 * k, 19 * k
d.arc([cx - r, cy - r, cx + r, cy + r], start=125, end=55, fill=GOLD, width=int(5 * k))

d.line([(32 * k, 36 * k), (41.2 * k, 26.8 * k)], fill=CREAM, width=int(4.5 * k))

pr = 4 * k
d.ellipse([32 * k - pr, 36 * k - pr, 32 * k + pr, 36 * k + pr], fill=GOLD)

img.save("docs/profile-pic-x.png", quality=95)
print("saved: docs/profile-pic-x.png", img.size)
