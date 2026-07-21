# -*- coding: utf-8 -*-
"""localday.py — dia civil de Brasilia (UTC-3), NAO o dia civil do runner.

O GitHub Actions roda em UTC; date.today() puro vira a pagina 3h adiantado
em relacao ao relogio do usuario. Na pratica isso fazia o card/thread do
"dia" comecar as 00:01 UTC = 21:01 no horario de Brasilia da NOITE ANTERIOR
-- pra quem esta em Brasilia, a thread de "hoje" parecia ja existir desde
ontem a noite, e nenhuma thread nova parecia comecar durante o dia (achado
do usuario 21/jul/2026). Fuso fixo -3, sem horario de verao (Brasil nao usa
DST desde 2019)."""
from datetime import datetime, timezone, timedelta

BR_TZ = timezone(timedelta(hours=-3))


def today():
    """Data civil em Brasilia agora — use no lugar de date.today() em
    qualquer lugar que decide 'o dia de hoje' pro usuario (acumulo de
    cards, virada de thread, seed de conteudo diario)."""
    return datetime.now(BR_TZ).date()
