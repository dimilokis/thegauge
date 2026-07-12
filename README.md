# gauge-live

Repo: **github.com/dimilokis/thegauge**

Backend + dashboard alfa do The Gauge: coleta dados da Binance (spot, via
`data-api.binance.vision`) a cada hora, calcula Gauge Score / Move / Driver /
Verdict do top-100 cripto por volume 24h, publica `docs/gauge_live.json` e
serve o dashboard em `docs/index.html`.

**Por que `data-api.binance.vision` e nao `fapi.binance.com`:** a API normal
da Binance devolve HTTP 451 (geo-block) para os IPs de datacenter dos runners
do GitHub Actions — TODA run falhava. O `data-api.binance.vision` e o espelho
publico oficial da Binance para market data (sem chave, sem conta, via CDN) e
nao tem esse bloqueio. E spot em vez de Futures, o que pro Gauge (klines
diarios) da na mesma; o filtro de universo exclui stablecoins, wrapped e as
acoes tokenizadas com sufixo B (NVDAB etc) que o spot lista.

**Fluxo automatico completo:** Actions roda de hora em hora -> commita
`docs/gauge_live.json` -> o Cloudflare (conectado ao repo) redeploya o site
sozinho -> thegauge.art atualizado. Zero passo manual, zero PC ligado.

---

## Como saber se esta funcionando

- Aba **Actions** do repo -> workflow "Update Gauge snapshot".
  Clica nele -> **Run workflow** -> **Run workflow** (botao verde).
- Espera ~2-3 min, atualiza a pagina do Actions — se ficar com um check
  verde, funcionou. Vai ter aparecido um commit novo "chore: refresh gauge
  snapshot".
- Abre <https://thegauge.art> e ve se o "updated X min ago" no topo bate
  com agora (o Cloudflare leva mais ~1 min pra redeployar apos o commit).

Se isso funcionar uma vez, ele roda sozinho pra sempre, de hora em hora,
de graca — nao precisa mais fazer nada.

## Postar no Twitter/X (manual, de graca — recomendado)

O jeito automatico via API do X custa ~$6/mes (pay-per-use) e nao vale a
pena pra 1 post por dia. Fica manual mesmo, mas rapido:

No terminal, dentro da pasta `LONG_TRAIL`:
```
python marketing/daily_post.py --refresh
```
Isso gera o tweet do dia (baseado no dado real) **e ja copia pro
clipboard**. E so abrir o X e Ctrl+V. Leva uns 30 segundos.

## Telegram (opcional, so quando quiser alertas)

1. No Telegram, fala com `@BotFather` -> `/newbot` -> guarda o **token**.
2. Cria um canal, adiciona o bot como admin, posta uma mensagem qualquer,
   abre no navegador `https://api.telegram.org/bot<TOKEN>/getUpdates` — o
   numero em `"chat":{"id":...}` e o **chat_id**.
3. No repo: **Settings -> Secrets and variables -> Actions -> New repository
   secret**: cria `TG_BOT_TOKEN` e `TG_CHAT_ID`.

Sem isso o pipeline roda normal, so pula o envio de alerta.

## Automatizar o post no X (opcional, ~$6/mes, so se quiser)

Guia completo (chaves, custos, secrets) esta em
`marketing/post_x.py` e no workflow `.github/workflows/post.yml` — ja
prontos, so nao ativados. Se um dia quiser ligar, e so gerar as 4 chaves em
developer.x.com e colar nos Secrets do repo (mesmo lugar do Telegram acima).

## Dominio proprio (opcional, bem depois)

**Settings -> Pages -> Custom domain** -> `app.thegauge.art`, e no Cloudflare
DNS (onde o `thegauge.art` ja esta) cria um registro **CNAME**: nome `app`,
destino `dimilokis.github.io`.

## Formato do JSON (`docs/gauge_live.json`)

```json
{
  "generated_at": "2026-07-09T20:27:54Z",
  "universe_size": 95,
  "assets": [
    {"symbol": "SOL", "price": 152.3, "ret_pct": -2.1, "score": 16.2,
     "sigma": 3.1, "from_btc_pct": 22, "is_market": false, "verdict": "Oversold"}
  ]
}
```
