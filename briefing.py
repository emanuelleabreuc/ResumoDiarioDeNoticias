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
    "G1 tecnologia": ["https://g1.globo.com/rss/g1/tecnologia/"],
    "G1 economia": ["https://g1.globo.com/rss/g1/economia/"],
}

VARIAVEIS_OBRIGATORIAS = [ "GEMINI_API_KEY" ]

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
HORARIO_DO_ENVIO = "09:00"
JANELA_HORAS = 24
MAX_NOTICIAS_POR_SETOR = 5



def carregar_segredos():
    """Lê o .env e encerra o programa se faltar alguma variável."""
    load_dotenv()

    faltando = [nome for nome in VARIAVEIS_OBRIGATORIAS if not os.getenv(nome)]
    if faltando:
        sys.exit(f"Variáveis obrigatórias faltando: {', '.join(faltando)}")

    return {nome: os.getenv(nome) for nome in VARIAVEIS_OBRIGATORIAS}


def main():
    segredos = carregar_segredos()

    print("Configuração carregada:")
    for nome, valor in segredos.items():
        print(f"  {nome}: carregada ({len(valor)} caracteres)")

    print(f"\nFuso: {FUSO_HORARIO} | Envio às {HORARIO_DO_ENVIO}")
    print(f"Setores ({len(SETORES)}):")
    for setor, feeds in SETORES.items():
        print(f"  - {setor}: {len(feeds)} feed(s)")


if __name__ == "__main__":
    main()
