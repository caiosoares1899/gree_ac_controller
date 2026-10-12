# gree_ac_controller 🌬️

Controle dos ar-condicionados **Gree** de casa, rápido e sem a nuvem da Gree.

```
PWA (index.html, GitHub Pages)  ⇄  Firebase RTDB  ⇄  bridge/ (Node, no PC de casa)  ⇄  UDP 7000  ⇄  Gree
```

- **`index.html`** — a página (instalável na tela inicial, iOS e Android). Visual "Marine Glass": aleta que mostra a posição real, ar que acompanha a ventilação, rajada no turbo, neve no modo Aquecer, histórico de quem mexeu. Abra com `?sim=1` pra ver a **demonstração** (sem Firebase, sem ponte).
- **`bridge/`** — a ponte que roda no PC (sempre ligado). Fala com os aparelhos por UDP usando [`gree-hvac-client`](https://www.npmjs.com/package/gree-hvac-client) e sincroniza com o Firebase.
- **`bridge/database.rules.gree.json`** — regras do Realtime Database (só e-mails em `gree/permitidos`). **Revisar antes de publicar** — não estão mescladas em nenhum arquivo de regras.

## Status

| Parte | Estado |
|---|---|
| Página + animações + modo demo | ✅ testada no navegador (demo) |
| Ponte (`bridge/`) | ⚠️ escrita, **ainda não testada** em aparelho real |
| Login Google + Firebase real | ⚠️ não testado (depende das regras e da ponte) |

## Rodar a ponte (Windows)

1. Instale o Node.js 18+.
2. `cd bridge && npm install`
3. `npm run descobrir` — lista os IPs dos Gree na rede (dê um IP fixo/reserva no roteador pra cada um).
4. Copie `config.example.json` → `config.json` e preencha IPs/ids.
5. Baixe uma chave de conta de serviço do Firebase (Console → Configurações → Contas de serviço) e salve como `bridge/service-account.json` (**nunca commitar** — já está no `.gitignore`).
6. `npm start`. Pra ficar sempre ligada: Agendador de Tarefas do Windows ("ao iniciar") ou `pm2`.

## Liberar quem pode usar

No Console do Firebase: `gree/permitidos/{email com "." trocado por ","}` = `true` (ex.: `fulano@gmail,com`).

## Modelo de dados

- `gree/aparelhos/{id}` — `nome`, `online`, `atualizado`, `estado{power,mode,temperature,currentTemperature,fanSpeed,turbo,swingVert,…}` (escrito pela ponte)
- `gree/comandos/{id}/{pushId}` — o app grava `{temperature: 22, ts, quem, uid}`; a ponte aplica e apaga
- `gree/historico/{id}/{pushId}` — `{campo, de, para, quem, origem, ts}` (escrito pela ponte; `origem: "aparelho"` = controle remoto/botão)
