# gauge-live

Backend real do The Gauge: coleta dados da Binance Futures a cada hora, calcula
Gauge Score / Move / Driver / Verdict para o top-100 por volume 24h, publica
`public/gauge_live.json` e manda alerta no Telegram quando um ativo fica
extremo (>=2.5 sigma) E independente de Bitcoin (<=40% explicado por BTC).

Repositorio separado do research privado (LONG_TRAIL) de proposito — este aqui
precisa ser publico para servir o JSON de graca via raw.githubusercontent.com.
Nao tem nenhuma estrategia de trading aqui, so o motor do produto.

## Setup (uma vez)

1. **Criar o repo no GitHub** (publico): vai em github.com/new, nome sugerido
   `gauge-live`, publico, sem README/gitignore (ja tem aqui).
2. Push deste conteudo:
   ```
   git init
   git add .
   git commit -m "feat: gauge live scoring engine + hourly workflow"
   git remote add origin https://github.com/<seu-usuario>/gauge-live.git
   git push -u origin main
   ```
3. **Criar o bot do Telegram**: abre o Telegram, procura `@BotFather`, manda
   `/newbot`, segue o fluxo. Ele te da um **token** (guarda).
4. **Pegar o chat_id**: cria um canal/grupo (pode ser so seu por enquanto),
   adiciona o bot como admin, manda uma mensagem qualquer no canal, depois abre
   no navegador:
   `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   e procura `"chat":{"id": ...}` na resposta — esse numero e o chat_id.
5. **Adicionar os secrets no GitHub**: no repo, Settings -> Secrets and
   variables -> Actions -> New repository secret:
   - `TG_BOT_TOKEN` = o token do BotFather
   - `TG_CHAT_ID` = o chat_id do passo 4
6. **Testar manualmente**: aba Actions do repo -> "Update Gauge snapshot" ->
   "Run workflow". Confere se `public/gauge_live.json` foi commitado no final.

Depois disso ele roda sozinho, todo hora, sem precisar tocar em nada.

## Consumir o JSON no site

Repo publico expoe o arquivo em:
```
https://raw.githubusercontent.com/<seu-usuario>/gauge-live/main/public/gauge_live.json
```
Esse endpoint manda CORS liberado, entao da pra `fetch()` direto do
thegauge.art sem servidor no meio. (Isso ainda nao esta ligado no
`coinpulse/index.html` — e o proximo passo, depois de confirmar que o
pipeline roda sozinho por uns dias.)

## Formato do JSON

```json
{
  "generated_at": "2026-07-08T20:08:36Z",
  "universe_size": 92,
  "assets": [
    {"symbol": "SOL", "score": 16.2, "sigma": 3.1, "from_btc_pct": 22, "is_market": false, "verdict": "Oversold"},
    {"symbol": "BTC", "score": 62.0, "sigma": 1.8, "from_btc_pct": 100, "is_market": true, "verdict": "Neutral"}
  ]
}
```
