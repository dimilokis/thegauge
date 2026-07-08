# gauge-live

Backend + dashboard alfa do The Gauge: coleta dados da Binance Futures a cada
hora, calcula Gauge Score / Move / Driver / Verdict para o top-100 cripto por
volume 24h (acoes tokenizadas/indices/commodities filtrados fora), publica
`docs/gauge_live.json`, serve o dashboard em `docs/index.html` via GitHub
Pages, e manda alerta no Telegram quando um ativo fica extremo (>=2.5 sigma)
E independente de Bitcoin (<=40% explicado por BTC).

Repositorio separado do research privado (LONG_TRAIL) de proposito — este
precisa ser publico. Nao tem nenhuma estrategia de trading aqui, so o motor
do produto.

## Publicar (uma vez, ~10 min)

1. **Criar o repo no GitHub** (publico): github.com/new, nome `gauge-live`,
   Public, sem README/gitignore (ja existem aqui). Nao inicializa nada.
2. **Push** (rodar dentro desta pasta):
   ```
   git remote add origin https://github.com/<SEU-USUARIO>/gauge-live.git
   git branch -M main
   git push -u origin main
   ```
   (se pedir login: `gh auth login` ou usa o Git Credential Manager que abre
   o navegador sozinho)
3. **Ativar o GitHub Pages**: no repo -> Settings -> Pages ->
   Source: "Deploy from a branch" -> Branch: `main`, Folder: `/docs` -> Save.
   Em ~2 min o dashboard fica no ar em:
   `https://<SEU-USUARIO>.github.io/gauge-live/`
4. **Testar o workflow**: aba Actions -> "Update Gauge snapshot" ->
   Run workflow. Confere se aparece um commit novo "chore: refresh gauge
   snapshot" e se o dashboard atualizou o "updated X min ago".
5. Pronto — a partir daqui atualiza sozinho toda hora, de graca, sem servidor.

## Telegram (opcional agora, necessario antes do launch dos alertas)

1. No Telegram, fala com `@BotFather` -> `/newbot` -> guarda o **token**.
2. Cria um canal, adiciona o bot como admin, posta qualquer mensagem, e abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador — o numero
   em `"chat":{"id":...}` e o **chat_id**.
3. No repo: Settings -> Secrets and variables -> Actions -> New repository
   secret: `TG_BOT_TOKEN` e `TG_CHAT_ID`.
Sem os secrets o pipeline roda normal, so pula o envio.

## Dominio proprio (opcional, depois)

Settings -> Pages -> Custom domain -> `app.thegauge.art`, e no Cloudflare DNS
cria um CNAME `app` -> `<SEU-USUARIO>.github.io`.

## Formato do JSON (`docs/gauge_live.json`)

```json
{
  "generated_at": "2026-07-08T20:27:54Z",
  "universe_size": 95,
  "assets": [
    {"symbol": "SOL", "price": 152.3, "ret_pct": -2.1, "score": 16.2,
     "sigma": 3.1, "from_btc_pct": 22, "is_market": false, "verdict": "Oversold"}
  ]
}
```
