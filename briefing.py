from dataclasses import dataclass
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests
import html
import re
from dotenv import load_dotenv
from google import genai




SETORES = {
    "Tecnologia": ["https://g1.globo.com/rss/g1/tecnologia/"],
    "Economia": ["https://g1.globo.com/rss/g1/economia/"],
}

VARIAVEIS_OBRIGATORIAS = [ "GEMINI_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID" ]

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
HORARIO_DO_ENVIO = "09:00"
JANELA_HORAS = 24
MAX_NOTICIAS_POR_SETOR = 5
MAX_CARACTERES_RESUMO = 300
EMOJIS = {"Tecnologia": "💻", "Economia": "📈"}

USER_AGENT = "ResumoDiarioDeNoticias/1.0 (projeto pessoal)"
TIMEOUT = 10  # segundos
PAUSA_ENTRE_FEEDS = 1  # segundos
MODELO_GEMINI = "gemini-3.6-flash"
PAUSA_ENTRE_CHAMADAS_IA = 2  # segundos

@dataclass
class Noticia:
    setor: str
    titulo: str
    link: str
    resumo: str
    fonte: str
    publicada_em: time.struct_time | None



def carregar_segredos():
    """Lê o .env e encerra o programa se faltar alguma variável"""
    load_dotenv()

    faltando = [nome for nome in VARIAVEIS_OBRIGATORIAS if not os.getenv(nome)]
    if faltando:
        sys.exit(f"Variáveis obrigatórias faltando: {', '.join(faltando)}")

    return {nome: os.getenv(nome) for nome in VARIAVEIS_OBRIGATORIAS}


def baixar_feed(url):
    """Baixa o feed RSS e retorna o conteúdo ou None se houver erro"""
    try:
        resposta = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        print(f"Erro ao baixar feed {url}: {erro}")
        return None

    return resposta.content

def extrair_noticias(conteudo, setor):
    """Extrai notícias do feed RSS e retorna uma lista de objetos Noticia"""
    feed = feedparser.parse(conteudo)

    if feed.bozo and not feed.entries:
        print(f" [aviso] feed inválido em '{setor}': {feed.bozo_exception}")
        return []

    fonte_do_feed = feed.feed.get("title", "Fonte desconhecida")
    noticias = []

    for entrada in feed.entries:
        titulo = entrada.get("title", "").strip()
        link = entrada.get("link", "").strip()
        if not titulo or not link:
            continue

        noticias.append(
            Noticia(
                setor=setor,
                titulo=titulo,
                link=link,
                resumo=entrada.get("summary", ""),
                fonte=entrada.get("source", {}).get("title") or fonte_do_feed,
                publicada_em=entrada.get("published_parsed") or entrada.get("updated_parsed"),
            )
        )

    return noticias

def coletar_todas(setores):
    """Percorre todos os feeds de todos os setores e junta as notícias"""
    todas = []

    for setor, urls in setores.items():
        for url in urls:
            conteudo = baixar_feed(url)
            if conteudo is not None:
                todas.extend(extrair_noticias(conteudo, setor))
            time.sleep(PAUSA_ENTRE_FEEDS)

    return todas


def converter_data(struct):
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc) #pega os 6 primeiros campos do struct_time: (ano, mês, dia, hora, minuto, segundo); o * desempacota; tzinfo=timezone.utc O tzinfo=timezone.utc marca a data como UTC, o que permite compará-la com o limite e convertê-la para o horário de Brasília

def filtrar_recentes(noticias, horas):
    """Filtra notícias publicadas nas últimas 'horas' horas"""
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    recentes = []
    for noticia in noticias:
        data = converter_data(noticia.publicada_em)
        if data is not None and data >= limite:
            recentes.append(noticia)
    return recentes

def remover_duplicadas(noticias):
    """Remove notícias duplicadas com base no título"""
    vistas = set()
    unicas = []
    for noticia in noticias:
        chave = noticia.titulo.rsplit(" - ", 1)[0].lower().strip()
        if chave not in vistas:
            vistas.add(chave)
            unicas.append(noticia)
    return unicas

def limpar_html(texto):
    """Remove tags e entidades HTML, junta espaços e corta o tamanho."""
    sem_tags = re.sub(r"<[^>]+>", " ", texto)
    sem_entidades = html.unescape(sem_tags)
    limpo = " ".join(sem_entidades.split())
    return limpo[:MAX_CARACTERES_RESUMO]

def agrupar_por_setor(noticias, setores, maximo):
    """Separa as notícias por setor, da mais recente para a mais antiga, até 'maximo' por setor"""
    por_setor = {setor: [] for setor in setores}

    for noticia in noticias:
        if noticia.setor in por_setor:
            por_setor[noticia.setor].append(noticia)

    for setor, lista in por_setor.items():
        ordenada = sorted(lista, key=lambda n: converter_data(n.publicada_em), reverse=True)
        por_setor[setor] = ordenada[:maximo]

    return por_setor

def enviar_telegram(texto, token, chat_id):
    """Envia a mensagem para o Telegram e retorna True se deu certo"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    dados = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    try:
        resposta = requests.post(url, json=dados, timeout=TIMEOUT)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        if erro.response is not None:
            print(f"Erro do Telegram ({erro.response.status_code}): {erro.response.text}")
        else:
            print(f"Erro de conexão com o Telegram: {type(erro).__name__}")
        return False

    return True

def dividir_mensagem(texto, limite=4000):
    """Quebra o texto em pedaços de até 'limite' caracteres, sem cortar blocos no meio"""
    pedacos = []
    atual = ""

    for bloco in texto.split("\n\n"):
        candidato = f"{atual}\n\n{bloco}" if atual else bloco
        if len(candidato) <= limite:
            atual = candidato
        else:
            if atual:
                pedacos.append(atual)
            atual = bloco

    if atual:
        pedacos.append(atual)

    return pedacos

def enviar_mensagem(texto, token, chat_id):
    """Divide a mensagem se necessário e envia cada pedaço; retorna True se tudo foi enviado"""
    tudo_certo = True
    for pedaco in dividir_mensagem(texto):
        if not enviar_telegram(pedaco, token, chat_id):
            tudo_certo = False
    return tudo_certo

def montar_prompt(setor, noticias):
    """Monta o texto enviado à IA com as notícias de um setor"""
    linhas = []
    for i, noticia in enumerate(noticias, start=1):
        linhas.append(f"{i}. {noticia.titulo} — {noticia.resumo}")
    lista = "\n".join(linhas)

    return (
        "Você é um editor de jornal que escreve resumos curtos e objetivos.\n\n"
        f"Escreva em português do Brasil um panorama de 2 a 3 frases sobre as notícias "
        f"de {setor} abaixo, destacando o que é mais importante.\n\n"
        "Regras:\n"
        "- Use apenas as informações fornecidas, não invente fatos.\n"
        "- Responda só com texto puro: sem markdown, sem asteriscos, sem títulos, sem listas.\n\n"
        f"Notícias:\n{lista}"
    )

def resumir_setor(cliente, setor, noticias):
    """Pede à IA um panorama do setor; retorna o texto ou None se não houver notícias ou der erro"""
    if not noticias:
        return None

    prompt = montar_prompt(setor, noticias)

    try:
        resposta = cliente.models.generate_content(model=MODELO_GEMINI, contents=prompt)
    except Exception as erro:
        print(f"  [aviso] IA falhou em '{setor}': {erro}")
        return None

    if not resposta.text:
        print(f"  [aviso] IA não devolveu texto em '{setor}'")
        return None

    return resposta.text.replace("*", "").strip()


def resumir_todos(cliente, noticias_por_setor):
    """Gera o panorama de cada setor e retorna {setor: texto ou None}"""
    resumos = {}
    for setor, noticias in noticias_por_setor.items():
        resumos[setor] = resumir_setor(cliente, setor, noticias)
        if noticias:
            time.sleep(PAUSA_ENTRE_CHAMADAS_IA)
    return resumos

def formatar_noticia(noticia):
    """Monta a linha de uma notícia: título com link e a fonte"""
    titulo = html.escape(noticia.titulo)
    fonte = html.escape(noticia.fonte)
    link = html.escape(noticia.link)
    return f'• <a href="{link}">{titulo}</a> — {fonte}'

def formatar_setor(setor, noticias, resumo):
    """Monta o bloco de um setor: título, panorama da IA e manchetes"""
    emoji = EMOJIS.get(setor, "📌")
    linhas = [f"{emoji} <b>{html.escape(setor)}</b>"]

    if not noticias:
        linhas.append("Sem novidades nas últimas 24h.")
        return "\n".join(linhas)

    if resumo:
        resumo_limpo = " ".join(resumo.split())
        linhas.append(f"<i>{html.escape(resumo_limpo)}</i>")

    for noticia in noticias:
        linhas.append(formatar_noticia(noticia))

    return "\n".join(linhas)

def formatar_mensagem(noticias_por_setor, resumos):
    """Junta o cabeçalho com a data e os blocos de todos os setores"""
    data = datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y")
    blocos = [f"📰 <b>Resumo do dia — {data}</b>"]

    for setor, noticias in noticias_por_setor.items():
        blocos.append(formatar_setor(setor, noticias, resumos.get(setor)))

    return "\n\n".join(blocos)

def main():
    segredos = carregar_segredos()

    print("Coletando notícias...")
    noticias = coletar_todas(SETORES)
    print(f"  {len(noticias)} notícias coletadas")

    noticias = filtrar_recentes(noticias, JANELA_HORAS)
    print(f"  {len(noticias)} publicadas nas últimas {JANELA_HORAS}h")

    noticias = remover_duplicadas(noticias)
    print(f"  {len(noticias)} após remover duplicadas")

    for noticia in noticias:
        noticia.resumo = limpar_html(noticia.resumo)

    noticias_por_setor = agrupar_por_setor(noticias, SETORES, MAX_NOTICIAS_POR_SETOR)
    for setor, lista in noticias_por_setor.items():
        print(f"  {setor}: {len(lista)} selecionadas")

    print("\nGerando resumos com IA...")
    cliente = genai.Client(api_key=segredos["GEMINI_API_KEY"])
    resumos = resumir_todos(cliente, noticias_por_setor)

    mensagem = formatar_mensagem(noticias_por_setor, resumos)

    print("\nEnviando para o Telegram...")
    enviado = enviar_mensagem(mensagem, segredos["TELEGRAM_TOKEN"], segredos["TELEGRAM_CHAT_ID"])
    if not enviado:
        sys.exit("Falha ao enviar o resumo para o Telegram.")

    print("  Resumo enviado!")


if __name__ == "__main__":
    main()
