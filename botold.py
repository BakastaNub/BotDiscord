import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
import datetime
import re
import sys
import asyncio
import json
import requests
from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup

# Ensure the script changes directory if it's running as a bundled executable
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

# Load environment variables from .env file
load_dotenv()

# Configuration constants
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ANYTHING_ID = int(os.getenv("CHANNEL_ANYTHING_ID"))
REENVIOS_CONFIG_FILE = "reenvios.json"
LAST_PROCESSED_ID_FILE = "ultimo_reenvio.txt"
LOG_FILE = "bot_activity.log"

# Configure Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

# Initialize the bot
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Global variables for configuration and state
reenvios_config = []
last_processed_message_id = 0

ALIAS_FILE = "aliases.json"
alias_map = {}

def load_aliases():
    global alias_map
    if not os.path.exists(ALIAS_FILE):
        alias_map = {}
        return
    try:
        with open(ALIAS_FILE, "r", encoding="utf-8") as f:
            alias_map = json.load(f)
        log_action("ALIAS", f"Cargados {len(alias_map)} alias")
    except Exception as e:
        log_action("ERROR", "Error al cargar alias", exception_obj=e)
        alias_map = {}

def save_aliases():
    try:
        with open(ALIAS_FILE, "w", encoding="utf-8") as f:
            json.dump(alias_map, f, indent=2, ensure_ascii=False)
        log_action("ALIAS", f"Guardados {len(alias_map)} alias")
    except Exception as e:
        log_action("ERROR", "Error al guardar alias", exception_obj=e)


def log_action(action, message=None, exception_obj=None):
    """
    Logs actions to both the console and an external log file.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if exception_obj:
        log_entry = f"❌ [{timestamp}] ERROR en {action}: {message or ''}. Detalles: {exception_obj}"
    elif message:
        log_entry = f"🔹 [{timestamp}] {action}: {message}"
    else:
        log_entry = f"📌 [{timestamp}] {action}"

    print(log_entry)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"❌ [{timestamp}] ERROR al escribir en log: {e}")

def load_reenvios_config():
    global reenvios_config
    try:
        if not os.path.exists(REENVIOS_CONFIG_FILE):
            log_action("ADVERTENCIA", f"No existe {REENVIOS_CONFIG_FILE}; se creará uno nuevo.")
            reenvios_config = []
            return
        with open(REENVIOS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            reenvios_config = json.load(f)
        for rule in reenvios_config:
            log_action("REGLA CARGADA", rule.get('name', 'sin nombre'))
    except Exception as e:
        log_action("ERROR", "Al cargar reenvíos", exception_obj=e)
        reenvios_config = []

def save_reenvios_config():
    try:
        with open(REENVIOS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(reenvios_config, f, indent=2)
        log_action("CONFIGURACIÓN GUARDADA")
    except Exception as e:
        log_action("ERROR", "Al guardar reenvíos", exception_obj=e)

def load_last_processed_id():
    global last_processed_message_id
    try:
        if os.path.exists(LAST_PROCESSED_ID_FILE):
            with open(LAST_PROCESSED_ID_FILE, 'r') as f:
                last_processed_message_id = int(f.read().strip())
            log_action("ÚLTIMO ID", last_processed_message_id)
        else:
            with open(LAST_PROCESSED_ID_FILE, 'w') as f:
                f.write("0")
            last_processed_message_id = 0
            log_action("ÚLTIMO ID", "Inicializado a 0")
    except Exception as e:
        log_action("ERROR", "Al cargar último ID", exception_obj=e)
        last_processed_message_id = 0

def save_last_processed_id(message_id):
    global last_processed_message_id
    if message_id > last_processed_message_id:
        last_processed_message_id = message_id
        try:
            with open(LAST_PROCESSED_ID_FILE, 'w') as f:
                f.write(str(message_id))
        except Exception as e:
            log_action("ERROR", "Al guardar último ID", exception_obj=e)