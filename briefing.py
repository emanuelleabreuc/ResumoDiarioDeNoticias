from dataclasses import dataclass
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests
from dotenv import load_dotenv
from google import genai




SETORES = {
    "Tecnologia": ["https://g1.globo.com/rss/g1/tecnologia/"],
    "Economia": ["https://g1.globo.com/rss/g1/economia/"],
}

VARIAVEIS_OBRIGATORIAS = [ "GEMINI_API_KEY" ]

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
HORARIO_DO_ENVIO = "09:00"
JANELA_HORAS = 24
MAX_NOTICIAS_POR_SETOR = 5


USER_AGENT = "ResumoDiarioDeNoticias/1.0 (projeto pessoal)"
TIMEOUT = 10  # segundos
PAUSA_ENTRE_FEEDS = 1  # segundos

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
    """Baixa e retorna o feed RSS como um objeto feedparser"""
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


def main():
    segredos = carregar_segredos()

    print("Configuração carregada:")
    for nome, valor in segredos.items():
        print(f"  {nome}: carregada ({len(valor)} caracteres)")

    print(f"\nFuso: {FUSO_HORARIO} | Envio às {HORARIO_DO_ENVIO}")

    print("Coletando notícias...")
    noticias = coletar_todas(SETORES)

    for setor in SETORES:
        do_setor = [n for n in noticias if n.setor == setor]
        print(f"\n{setor}: {len(do_setor)} notícias coletadas")
        for noticia in do_setor[:3]:
            print(f"  - {noticia.titulo} ({noticia.fonte})")


def converter_data(struct):
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc) #pega os 6 primeiros campos do struct_time: (ano, mês, dia, hora, minuto, segundo); o * desempacota; tzinfo=timezone.utc O tzinfo=timezone.utc marca a data como UTC, o que permite compará-la com o limite e convertê-la para o horário de Brasília




if __name__ == "__main__":
    main()
