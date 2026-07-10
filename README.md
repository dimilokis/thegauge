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

## Postagem automatica no X (1x/dia, sem copiar/colar)

Custo real (fevereiro/2026 em diante, pay-per-use): ~$0.015 por post + $0.20
se tiver link = **~$0.215/post**. Postando 1x/dia: **~$6.45/mes**. Sem
assinatura, sem plano fixo.

1. Cria conta em [developer.x.com](https://developer.x.com) (pode ser com a
   mesma conta do X que vai postar).
2. Cria um **App** novo, permissao **Read and Write**.
3. Gera as 4 chaves: **API Key**, **API Key Secret**, **Access Token**,
   **Access Token Secret** (o Access Token precisa ser gerado DEPOIS de
   marcar Read+Write, senao sai read-only).
4. Configura o billing (pay-per-use) com um cartao — sem isso a API bloqueia
   a chamada de escrita.
5. No repo do GitHub: Settings -> Secrets and variables -> Actions -> New
   repository secret, um pra cada:
   `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`.
6. (Opcional) Settings -> Secrets and variables -> Actions -> aba
   **Variables** -> New variable `DASHBOARD_URL` = a URL real do dashboard
   (ex: `https://<usuario>.github.io/gauge-live/`). Sem isso usa
   `https://thegauge.art` como padrao.
7. Testar: aba Actions -> "Daily X post" -> Run workflow. Confere se o tweet
   saiu na conta.

Dali em diante posta sozinho todo dia as 13:00 UTC (~10h Brasilia), sem voce
tocar em nada. Reddit continua manual de proposito — postar por API la tem
risco real de ban/remocao por automod, e o que faz o post sobreviver e
parecer analise genuina, nao bot.

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
