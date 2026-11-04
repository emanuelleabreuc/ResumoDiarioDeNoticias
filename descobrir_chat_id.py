import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")
chat_id_atual = os.getenv("TELEGRAM_CHAT_ID")

if not token:
    sys.exit("TELEGRAM_TOKEN não está no .env")

base = f"https://api.telegram.org/bot{token}"

# 1. Qual bot é esse token?
bot = requests.get(f"{base}/getMe", timeout=10).json()
if not bot.get("ok"):
    sys.exit(f"Token inválido: {bot.get('description')}")
print(f"Token pertence ao bot: @{bot['result']['username']} (id {bot['result']['id']})")

# 2. Quem mandou mensagem para esse bot?
updates = requests.get(f"{base}/getUpdates", timeout=10).json().get("result", [])
chats = {}
for update in updates:
    mensagem = update.get("message") or update.get("edited_message") or update.get("my_chat_member") or {}
    chat = mensagem.get("chat")
    if chat:
        nome = chat.get("first_name") or chat.get("title") or ""
        chats[chat["id"]] = nome

print(f"\nTELEGRAM_CHAT_ID no seu .env: {chat_id_atual!r}")
if not chats:
    print("Nenhuma conversa encontrada. Mande uma mensagem para o bot acima e rode de novo.")
else:
    print("Conversas encontradas (use um destes números):")
    for chat_id, nome in chats.items():
        marca = "  <-- igual ao .env" if str(chat_id) == (chat_id_atual or "").strip() else ""
        print(f"  {chat_id}  ({nome}){marca}")