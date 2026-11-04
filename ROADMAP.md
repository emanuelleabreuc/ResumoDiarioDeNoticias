# Roteiro — Resumo Diário de Notícias

Objetivo final: **todo dia às 9h (horário de Brasília)** o sistema coleta notícias dos
setores que te interessam, gera um resumo com IA (Gemini) e **envia pelo Telegram**.

---

## 1. Onde o projeto está hoje

O fluxo completo tem 7 passos. Os 4 primeiros já estão feitos em `briefing.py`:

```
[1] Coletar feeds RSS        ✅ baixar_feed, extrair_noticias, coletar_todas
[2] Filtrar últimas 24h      ✅ converter_data, filtrar_recentes
[3] Remover duplicadas       ✅ remover_duplicadas
[4] Limpar HTML do resumo    ✅ limpar_html
[5] Selecionar por setor     ⬜ ordenar por data + limitar a MAX_NOTICIAS_POR_SETOR
[6] Resumir com IA           ⬜ Gemini
[7] Formatar e enviar        ⬜ Telegram
[+] Rodar todo dia às 9h     ⬜ agendamento (GitHub Actions)
```

O que já existe e ainda **não é usado**:

| Item | Situação |
|---|---|
| `from google import genai` | importado, mas nenhuma função chama o Gemini |
| `MAX_NOTICIAS_POR_SETOR = 5` | definido, nunca aplicado |
| `HORARIO_DO_ENVIO = "09:00"` | só aparece num `print`; nada agenda a execução |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | estão no `.env.exemplo`, mas não em `VARIAVEIS_OBRIGATORIAS` |
| `main()` | ainda é uma versão de depuração (imprime 3 notícias por setor) |

---

## Etapa 0 — Pequenos ajustes no que já existe

Faça antes de tudo, é rápido.

1. **Adicionar as variáveis do Telegram** em `VARIAVEIS_OBRIGATORIAS`:
   ```python
   VARIAVEIS_OBRIGATORIAS = ["GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
   ```
   Assim `carregar_segredos()` já devolve as três e o programa para cedo se faltar alguma.

2. **Corrigir docstrings** que não batem com o código:
   - `baixar_feed`: diz que retorna "objeto feedparser", mas retorna `bytes` (`resposta.content`) ou `None`.
   - `remover_duplicadas`: diz "título e link", mas a chave usa só o título.

3. **Criar seu `.env` local** (copie o `.env.exemplo`). As chaves do Gemini e do Telegram
   você vai obter nas etapas 2 e 3 — pode deixar em branco por enquanto.

4. **Confirmar que os feeds respondem** rodando `python briefing.py` na sua máquina.
   Você deve ver "N notícias coletadas" com N > 0. Se der 0, abra a URL do feed no navegador.

> Commit sugerido: `ajustes: variáveis do telegram e docstrings`

---

## Etapa 1 — Selecionar as notícias de cada setor

**Função nova:** `agrupar_por_setor(noticias, setores, maximo)`

| | |
|---|---|
| Recebe | a lista de `Noticia` já filtrada/limpa, o dicionário `SETORES` e `MAX_NOTICIAS_POR_SETOR` |
| Retorna | `dict` → `{"Tecnologia": [Noticia, ...], "Economia": [...]}` |
| Responsabilidade | separar por setor, ordenar da mais recente para a mais antiga e cortar no máximo |

Passo a passo:
1. Crie um dicionário com uma lista vazia para **cada setor de `SETORES`**
   (assim setores sem notícia aparecem com lista vazia, em vez de sumirem).
2. Percorra as notícias e coloque cada uma na lista do seu `noticia.setor`.
3. Ordene cada lista com `sorted(..., key=..., reverse=True)`. Use como chave
   `converter_data(n.publicada_em)` — você já tem essa função.
4. Corte com fatiamento: `lista[:maximo]`.

Como testar: no `main`, imprima `{setor: len(lista)}` — nenhum valor deve passar de 5.

> Commit sugerido: `função agrupar por setor`

---

## Etapa 2 — Criar o bot do Telegram (configuração manual)

Nada de código aqui, só obter o **token** e o **chat_id**.

1. No Telegram, abra uma conversa com **@BotFather**.
2. Envie `/newbot`, escolha um nome e um username terminado em `bot`.
3. O BotFather responde com um token no formato `123456789:AAH...`.
   → coloque em `TELEGRAM_BOT_TOKEN` no `.env`. **Nunca faça commit desse valor.**
4. Abra a conversa com o seu bot novo e mande qualquer mensagem (ex.: "oi").
   *Sem isso o bot não consegue te enviar nada.*
5. No navegador, acesse (trocando `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. No JSON que aparecer, procure `"chat":{"id": 987654321 ...}`.
   → esse número vai em `TELEGRAM_CHAT_ID`.

---

## Etapa 3 — Enviar mensagem pelo Telegram

Faça o envio **antes** da IA: assim você já consegue testar o sistema de ponta a ponta
com uma mensagem simples.

### 3.1 `enviar_telegram(texto, token, chat_id)`

| | |
|---|---|
| Recebe | o texto já formatado, o token e o chat_id |
| Retorna | `True` se enviou, `False` se falhou |
| Responsabilidade | fazer o POST na API do Telegram e tratar erros |

Detalhes da API:
- URL: `https://api.telegram.org/bot{token}/sendMessage`
- Envie com `requests.post(url, json={...}, timeout=TIMEOUT)` e o corpo:
  ```python
  {
      "chat_id": chat_id,
      "text": texto,
      "parse_mode": "HTML",              # permite <b>, <i>, <a href="...">
      "disable_web_page_preview": True,  # evita um card gigante do 1º link
  }
  ```
- Use o mesmo padrão de `baixar_feed`: `try` / `raise_for_status()` / `except requests.RequestException`.
- Quando der erro, imprima também `resposta.text` — o Telegram explica o motivo ali
  (ex.: `"can't parse entities"` = HTML inválido na mensagem).

Teste: no `main`, chame `enviar_telegram("Olá do <b>briefing</b>!", ...)` e veja chegar no celular.

### 3.2 `dividir_mensagem(texto, limite=4000)`

O Telegram aceita **no máximo 4096 caracteres por mensagem**.

| | |
|---|---|
| Recebe | o texto completo |
| Retorna | lista de pedaços, cada um com até `limite` caracteres |
| Responsabilidade | quebrar **entre blocos/linhas**, nunca no meio de uma tag HTML |

Dica: separe o texto por `"\n\n"` (fim de cada setor) e vá juntando blocos num pedaço
enquanto couber; quando não couber, comece um pedaço novo. Depois, no envio, faça um
`for` mandando cada pedaço.

> Commit sugerido: `função enviar telegram`

---

## Etapa 4 — Resumir com IA (Gemini)

### 4.1 Obter a chave
1. Acesse **Google AI Studio** (aistudio.google.com) → "Get API key" → crie uma chave.
2. Coloque em `GEMINI_API_KEY` no `.env`.
3. Crie uma constante com o modelo, ex.: `MODELO_GEMINI = "gemini-2.5-flash"`.
   Confira na documentação do Gemini qual é o modelo "Flash" atual — os nomes mudam
   com o tempo, e deixar numa constante facilita trocar.

### 4.2 Decisão de design importante

**Peça para a IA devolver só texto puro**, e deixe o *seu código* montar o HTML
(títulos, links, negrito). Se a IA gerar HTML ou markdown, uma tag mal fechada faz o
Telegram recusar a mensagem inteira. Separando as responsabilidades:
- IA → escreve um *panorama* curto do setor (2–3 frases)
- Código → lista as manchetes com links, que vêm direto do RSS (não dá para a IA inventar link)

### 4.3 `montar_prompt(setor, noticias)`

| | |
|---|---|
| Recebe | o nome do setor e a lista de notícias dele |
| Retorna | `str` com o prompt |

O prompt deve conter:
- O papel: "Você é um editor de jornal..."
- A tarefa: "Escreva em português do Brasil um panorama de 2 a 3 frases sobre as notícias de {setor} abaixo."
- As regras: "Use apenas as informações fornecidas, não invente fatos. Responda só com texto
  puro, sem markdown, sem asteriscos, sem títulos."
- As notícias numeradas: `1. {titulo} — {resumo}` (o `resumo` já foi limpo por `limpar_html`).

### 4.4 `resumir_setor(cliente, setor, noticias)`

| | |
|---|---|
| Recebe | o cliente do Gemini, o setor e as notícias |
| Retorna | `str` com o panorama, ou `None` se falhar |

Uso da biblioteca `google-genai` (já está no `requirements.txt`):
```python
cliente = genai.Client(api_key=segredos["GEMINI_API_KEY"])   # crie UMA vez no main
resposta = cliente.models.generate_content(model=MODELO_GEMINI, contents=prompt)
texto = resposta.text
```
Cuidados:
- Se a lista do setor estiver vazia, **não chame a IA** — retorne `None`.
- Envolva a chamada em `try/except Exception` e retorne `None` no erro. O resumo da IA
  é um "extra": se ela falhar, a mensagem ainda sai só com as manchetes.
- Por segurança, faça `texto.replace("*", "").strip()` (o Gemini às vezes insiste em markdown).
- O plano gratuito tem limite de requisições por minuto. Com poucos setores, uma chamada
  por setor está ok; se crescer muito, coloque um `time.sleep` entre as chamadas.

### 4.5 `resumir_todos(cliente, noticias_por_setor)`
Percorre o dicionário da Etapa 1 e devolve `{"Tecnologia": "panorama...", "Economia": None, ...}`.

> Commit sugerido: `função resumir com gemini`

---

## Etapa 5 — Montar a mensagem final

**Função nova:** `formatar_mensagem(noticias_por_setor, resumos)`

| | |
|---|---|
| Recebe | o dicionário da Etapa 1 e o dicionário de resumos da Etapa 4 |
| Retorna | `str` em HTML do Telegram |

Formato sugerido:
```
📰 Resumo do dia — 04/11/2026

💻 Tecnologia
Panorama gerado pela IA em 2–3 frases...
• Título da notícia 1 (link) — g1
• Título da notícia 2 (link) — g1

📈 Economia
...
```

Passo a passo:
1. Data no fuso certo: `datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y")`.
2. Para cada setor: nome em `<b>...</b>`, depois o resumo (se não for `None`), depois as manchetes.
3. Manchete como link: `f'• <a href="{link}">{titulo}</a> — {fonte}'`.
4. **Escape obrigatório**: todo texto vindo de fora (título, fonte, resumo da IA) passa por
   `html.escape(...)` antes de entrar na mensagem. Um título com `&` ou `<` quebra o HTML
   e o Telegram recusa o envio. O módulo `html` já está importado.
5. Setor sem notícias: escreva "Sem novidades nas últimas 24h." em vez de pular.
6. Separe os setores com `"\n\n"` — é o que `dividir_mensagem` usa para quebrar.

Opcional: um dicionário `EMOJIS = {"Tecnologia": "💻", "Economia": "📈"}`.

> Commit sugerido: `função formatar mensagem`

---

## Etapa 6 — Reescrever o `main()` como o fluxo final

Troque a parte de depuração pelo pipeline completo:

```
segredos            = carregar_segredos()
noticias            = coletar_todas(SETORES)
noticias            = filtrar_recentes(noticias, JANELA_HORAS)
noticias            = remover_duplicadas(noticias)
(limpar_html em cada resumo)
noticias_por_setor  = agrupar_por_setor(noticias, SETORES, MAX_NOTICIAS_POR_SETOR)
cliente             = genai.Client(...)
resumos             = resumir_todos(cliente, noticias_por_setor)
mensagem            = formatar_mensagem(noticias_por_setor, resumos)
para cada pedaço em dividir_mensagem(mensagem): enviar_telegram(...)
```

Regras de comportamento:
- Mantenha prints curtos de progresso (eles viram o log da execução agendada).
- Se **nenhum** envio der certo, termine com `sys.exit(1)`. Isso faz a execução aparecer
  como ❌ falha no GitHub Actions e você fica sabendo.
- Se não houver nenhuma notícia em nenhum setor, decida: mandar "Nada novo hoje" ou não
  mandar nada (recomendo mandar, para saber que o sistema rodou).

Teste completo: `python briefing.py` → a mensagem chega no Telegram. ✅

> Commit sugerido: `main com fluxo completo`

---

## Etapa 7 — Agendar para rodar todo dia às 9h

Recomendado: **GitHub Actions** — gratuito, não precisa deixar computador ligado, e o
código já está no GitHub.

### 7.1 Cadastrar os segredos no GitHub
Repositório → **Settings → Secrets and variables → Actions → New repository secret**.
Crie três: `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
(O `.env` não vai para o GitHub — está no `.gitignore` — então é por aqui que o robô recebe as chaves.)

### 7.2 Criar `.github/workflows/resumo-diario.yml`

```yaml
name: Resumo diário

on:
  schedule:
    - cron: "0 12 * * *"   # 12:00 UTC = 09:00 em Brasília
  workflow_dispatch:        # botão "Run workflow" para testar na hora

jobs:
  enviar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python briefing.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

Por que funciona sem `.env`: `load_dotenv()` não acha arquivo e não faz nada, e
`os.getenv` lê as variáveis que o workflow injetou.

### 7.3 Pontos de atenção
- **O cron do GitHub é em UTC.** O Brasil não tem horário de verão desde 2019, então
  `0 12` = 9h o ano todo. Se um dia voltar o horário de verão, ajuste.
- **Agendamentos só rodam na branch padrão (`main`).** Hoje a `main` só tem o commit
  inicial — o código precisa ser mesclado nela (Etapa 9) para o agendamento valer.
- **Pode atrasar alguns minutos** (às vezes mais) em horários cheios como hora cheia.
  Se quiser chegar antes das 9h, use por exemplo `"50 11 * * *"`.
- **Repositório público sem commits por 60 dias** tem os agendamentos desativados
  automaticamente; o GitHub avisa por e-mail e basta reativar na aba Actions.
- A constante `HORARIO_DO_ENVIO` passa a ser só informativa — quem manda é o cron.
  Pode remover ou deixar um comentário dizendo isso.

Teste: aba **Actions → Resumo diário → Run workflow**. Deve chegar a mensagem.

*Alternativa sem GitHub Actions:* `cron` num computador/servidor Linux sempre ligado:
`0 9 * * * cd /caminho/do/projeto && .venv/bin/python briefing.py >> briefing.log 2>&1`
(com o fuso da máquina em America/Sao_Paulo).

> Commit sugerido: `agendamento diário com github actions`

---

## Etapa 8 — Melhorias (depois que estiver funcionando)

Em ordem de utilidade:

1. **Mais setores e fontes** — adicione no dicionário `SETORES`. Antes, abra a URL do
   RSS no navegador para confirmar que é um feed válido. Ter 2+ fontes por setor é onde
   o `remover_duplicadas` passa a fazer diferença.
2. **Aviso de erro no Telegram** — envolva o corpo do `main` em `try/except` e, se algo
   quebrar, mande "⚠️ O resumo de hoje falhou: {erro}" pelo próprio `enviar_telegram`.
3. **Testes com `pytest`** (pasta `tests/`) para as funções puras, que não acessam internet:
   `limpar_html`, `remover_duplicadas`, `filtrar_recentes`, `agrupar_por_setor`,
   `dividir_mensagem`, `formatar_mensagem`. Ex.: garantir que um título com `&` sai escapado.
4. **Trocar `print` por `logging`** — dá níveis (INFO/WARNING/ERROR) e horário em cada linha.
5. **`README.md`** — o que o projeto faz, como configurar o `.env`, como rodar.

---

## Etapa 9 — Publicar na `main`

1. Abra um Pull Request desta branch para a `main` e faça o merge.
2. Confira em **Actions** que o workflow aparece e rode manualmente uma vez.
3. No dia seguinte, confirme que chegou sozinho às ~9h. 🎉

---

## Checklist geral

- [ ] Etapa 0 — variáveis do Telegram em `VARIAVEIS_OBRIGATORIAS`, docstrings, `.env`
- [ ] Etapa 1 — `agrupar_por_setor`
- [ ] Etapa 2 — bot criado, token e chat_id no `.env`
- [ ] Etapa 3 — `enviar_telegram`, `dividir_mensagem` (testado com "Olá")
- [ ] Etapa 4 — chave Gemini, `montar_prompt`, `resumir_setor`, `resumir_todos`
- [ ] Etapa 5 — `formatar_mensagem` com `html.escape`
- [ ] Etapa 6 — `main` final, `sys.exit(1)` em falha
- [ ] Etapa 7 — secrets no GitHub + workflow com cron `0 12 * * *`
- [ ] Etapa 8 — melhorias (opcional)
- [ ] Etapa 9 — merge na `main` e teste manual no Actions
