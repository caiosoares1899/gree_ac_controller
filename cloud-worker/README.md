# cloud-worker — Gree 100% online (sem nada ligado em casa)

Serviço Python que fica **sempre ligado na nuvem**: faz login no Gree+ (`greeclimate-davo22`), conversa com a nuvem da Gree por MQTT e sincroniza com o mesmo Firebase da página (`gree/comandos`, `gree/aparelhos`, `gree/historico`). O `index.html` não muda.

> ⚠️ Usa a API **não oficial** do Gree+ (engenharia reversa) e o **seu login do Gree+**. Pode quebrar se a Gree mudar algo. Use uma senha que você possa trocar e guarde-a só como variável secreta do host — nunca no código.

## Status
| Parte | Estado |
|---|---|
| Login, listar aparelho, ler estado (`../cloud-test/probe.py`) | ✅ testado com aparelho real |
| Tradução de valores e leitura de comandos (`test_mapeamento.py`) | ✅ testada |
| `main.py` (enviar comandos, histórico, reconexão) | ⚠️ escrito, **ainda não rodou de ponta a ponta** |

## Variáveis de ambiente
| Variável | Exemplo |
|---|---|
| `GREE_USER` / `GREE_PASS` | e-mail e senha do Gree+ (secretas) |
| `GREE_SERVER` | `South American` (padrão) |
| `FIREBASE_DB_URL` | `https://gree-ac-controller-default-rtdb.firebaseio.com` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | o **conteúdo** do JSON da conta de serviço (secreta) |
| `GREE_NOMES` | `9424b8ab167f=Quarto,aabbccddeeff=Sala` (opcional) |
| `POLL_SECONDS` | `10` (padrão) |
| `SOMENTE_LEITURA` | `1` = só lê e publica; ignora comandos da página |

## 1º teste (grátis, no Google Colab — antes de pagar hospedagem)
Faça upload do `service-account.json`, e numa célula:
```
!git clone -q -b claude/busy-gates-ahgvse https://github.com/caiosoares1899/gree_ac_controller
%cd gree_ac_controller/cloud-worker
!pip install -q -r requirements.txt
import os
os.environ.update(GREE_USER="...", GREE_PASS="...", FIREBASE_DB_URL="https://gree-ac-controller-default-rtdb.firebaseio.com",
                  FIREBASE_CREDENTIALS_PATH="/content/service-account.json", GREE_NOMES="9424b8ab167f=Quarto")
!python -u main.py
```
Deixe rodando e use a página: os comandos devem chegar no ar. (O Colab desliga sozinho depois de um tempo — serve só para testar.)

## Hospedagem (precisa ficar ligado 24h — a conexão MQTT é contínua)
Cloud Function **não serve** (não mantém conexão aberta). Opções, a conferir preço atual:
- **Google Cloud e2-micro (Always Free)** — grátis em algumas regiões dos EUA, exige cartão cadastrado.
- **Fly.io / Railway / Render (worker)** — poucos dólares por mês; o plano grátis do Render hiberna e derrubaria a conexão.
Use o `Dockerfile` desta pasta (ou `pip install -r requirements.txt && python main.py` numa VM).

## Testes locais
`python test_mapeamento.py` (sem rede).
