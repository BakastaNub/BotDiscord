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
import time
from pathlib import Path

# =============================================
# 1. Configuración inicial de archivos (NUEVO)
# =============================================
def setup_required_files():
    """Crea config.json y bot_activity.log si no existen."""
    # Crear config.json con valores por defecto
    if not os.path.exists("config.json"):
        default_config = {
            "reenvios_config": [],
            "last_processed_message_id": 0,
            "alias_map": {},
            "channel_anything_id": None
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print("✅ config.json creado automáticamente.")

    # Crear archivo de log vacío
    if not os.path.exists("bot_activity.log"):
        Path("bot_activity.log").touch()
        print("✅ bot_activity.log creado automáticamente.")

# =============================================
# 2. Función resource_path (MODIFICADA)
# =============================================
def resource_path(relative_path):
    """Obtiene la ruta absoluta para archivos externos"""
    if getattr(sys, 'frozen', False):
        # Si estamos ejecutando como un ejecutable empaquetado
        base_path = os.path.dirname(sys.executable)
    else:
        # Si estamos ejecutando en desarrollo
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# Llamada a la configuración inicial ANTES de cargar el bot
setup_required_files()

# Cargar .env desde la ruta correcta
load_dotenv(dotenv_path=resource_path(".env"))

# Constantes
TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = "config.json"
LOG_FILE = "bot_activity.log"

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

# Bot
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Variables de configuración global
bot_config = {
    "reenvios_config": [],
    "last_processed_message_id": 0,
    "alias_map": {},
    "channel_anything_id": None
}

# CACHE para Hiscores de jugadores
player_hiscores_cache = {}
CACHE_EXPIRY_SECONDS = 300  # 5 minutos

def log_action(action, message=None, exception_obj=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if exception_obj:
        log_entry = f"❌ [{timestamp}] ERROR en {action}: {message or ''}. Detalles: {exception_obj}"
    elif message:
        log_entry = f"🔹 [{timestamp}] {action}: {message}"
    else:
        log_entry = f"📌 [{timestamp}] {action}"
    print(log_entry)
    try:
        with open(resource_path(LOG_FILE), 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"❌ [{timestamp}] ERROR al escribir en log: {e}")

def load_config():
    global bot_config
    config_path = resource_path(CONFIG_FILE)
    log_action("CARGANDO CONFIGURACIÓN", f"Intentando cargar desde {config_path}")
    
    # Check for old files and migrate data
    old_reenvios_file = resource_path("reenvios.json")
    old_aliases_file = resource_path("aliases.json")
    old_last_id_file = resource_path("ultimo_reenvio.txt")

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
            
            # Cargar los valores existentes, usando valores por defecto si no existen
            bot_config["reenvios_config"] = loaded_config.get("reenvios_config", [])
            bot_config["last_processed_message_id"] = loaded_config.get("last_processed_message_id", 0)
            bot_config["alias_map"] = loaded_config.get("alias_map", {})
            bot_config["channel_anything_id"] = loaded_config.get("channel_anything_id", None) # Cargar el nuevo ID del canal

            log_action("CARGA DE CONFIGURACIÓN", f"Cargado {CONFIG_FILE} exitosamente.")
        except json.JSONDecodeError as e:
            log_action("ERROR", f"Error al decodificar {CONFIG_FILE}, el archivo podría estar corrupto. Recreando...", exception_obj=e)
            bot_config = {
                "reenvios_config": [],
                "last_processed_message_id": 0,
                "alias_map": {},
                "channel_anything_id": None # Inicializar en caso de corrupción
            }
            save_config() # Guardar una configuración vacía para prevenir futuros errores
        except Exception as e:
            log_action("ERROR", f"Error al cargar {CONFIG_FILE}", exception_obj=e)
            bot_config = {
                "reenvios_config": [],
                "last_processed_message_id": 0,
                "alias_map": {},
                "channel_anything_id": None # Inicializar en caso de error
            }
            save_config()
    else:
        log_action("ADVERTENCIA", f"No se encontró {CONFIG_FILE}. Se intentará migrar datos existentes o crear uno nuevo.")
        bot_config = {
            "reenvios_config": [],
            "last_processed_message_id": 0,
            "alias_map": {},
            "channel_anything_id": None # Inicializar si no existe config.json
        }
        
    # --- Migration Logic ---
    migrated_any = False

    # Migrate reenvios_config
    if os.path.exists(old_reenvios_file):
        log_action("MIGRACIÓN", f"Detectado {old_reenvios_file}. Intentando migrar reglas de reenvío.")
        try:
            with open(old_reenvios_file, 'r', encoding='utf-8') as f:
                old_reenvios = json.load(f)
            if old_reenvios and not bot_config["reenvios_config"]:
                bot_config["reenvios_config"] = old_reenvios
                log_action("MIGRACIÓN", "Reglas de reenvío migradas de reenvios.json. Eliminando archivo antiguo.")
                migrated_any = True
                os.remove(old_reenvios_file)
            elif old_reenvios and bot_config["reenvios_config"]:
                log_action("MIGRACIÓN", "Las reglas de reenvío ya existen en config.json. Saltando migración de reenvios.json.")
                # Optionally, merge or compare here if you want to keep both
                os.remove(old_reenvios_file) # Still remove to clean up
        except Exception as e:
            log_action("ERROR", "Error al migrar reenvios.json", exception_obj=e)

    # Migrate alias_map
    if os.path.exists(old_aliases_file):
        log_action("MIGRACIÓN", f"Detectado {old_aliases_file}. Intentando migrar alias.")
        try:
            with open(old_aliases_file, "r", encoding="utf-8") as f:
                old_aliases = json.load(f)
            if old_aliases and not bot_config["alias_map"]:
                bot_config["alias_map"] = old_aliases
                log_action("MIGRACIÓN", "Alias migrados de aliases.json. Eliminando archivo antiguo.")
                migrated_any = True
                os.remove(old_aliases_file)
            elif old_aliases and bot_config["alias_map"]:
                log_action("MIGRACIÓN", "Los alias ya existen en config.json. Saltando migración de aliases.json.")
                os.remove(old_aliases_file) # Still remove to clean up
        except Exception as e:
            log_action("ERROR", "Error al migrar aliases.json", exception_obj=e)

    # Migrate last_processed_message_id
    if os.path.exists(old_last_id_file):
        log_action("MIGRACIÓN", f"Detectado {old_last_id_file}. Intentando migrar último ID procesado.")
        try:
            with open(old_last_id_file, 'r') as f:
                old_last_id = int(f.read().strip())
            if old_last_id > bot_config["last_processed_message_id"]:
                bot_config["last_processed_message_id"] = old_last_id
                log_action("MIGRACIÓN", f"Último ID procesado migrado de ultimo_reenvio.txt: {old_last_id}. Eliminando archivo antiguo.")
                migrated_any = True
                os.remove(old_last_id_file)
            else:
                log_action("MIGRACIÓN", f"El último ID en config.json ({bot_config['last_processed_message_id']}) es más reciente o igual. Saltando migración de ultimo_reenvio.txt.")
                os.remove(old_last_id_file) # Still remove to clean up
        except Exception as e:
            log_action("ERROR", "Error al migrar ultimo_reenvio.txt", exception_obj=e)
            
    if migrated_any or not os.path.exists(config_path):
        log_action("GUARDANDO CONFIGURACIÓN", "Guardando cambios después de la migración o creación inicial.")
        save_config()

def save_config():
    config_path = resource_path(CONFIG_FILE)
    log_action("GUARDANDO CONFIGURACIÓN", f"Intentando guardar la configuración actual en {config_path}.")
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(bot_config, f, indent=2, ensure_ascii=False)
        log_action("GUARDADO DE CONFIGURACIÓN", f"Configuración guardada exitosamente en {CONFIG_FILE}.")
    except Exception as e:
        log_action("ERROR", f"Al guardar {CONFIG_FILE}", exception_obj=e)

# Update functions to use bot_config
def get_reenvios_config():
    log_action("ACCESO CONFIG", "Obteniendo reglas de reenvío.")
    return bot_config["reenvios_config"]

def set_reenvios_config(new_config):
    log_action("ACTUALIZANDO CONFIG", "Estableciendo nuevas reglas de reenvío.")
    bot_config["reenvios_config"] = new_config
    save_config()

def get_alias_map():
    log_action("ACCESO CONFIG", "Obteniendo mapa de alias.")
    return bot_config["alias_map"]

def set_alias_map(new_map):
    log_action("ACTUALIZANDO CONFIG", "Estableciendo nuevo mapa de alias.")
    bot_config["alias_map"] = new_map
    save_config()

def get_last_processed_id():
    log_action("ACCESO CONFIG", "Obteniendo último ID de mensaje procesado.")
    return bot_config["last_processed_message_id"]

def set_last_processed_id(message_id):
    log_action("ACTUALIZANDO CONFIG", f"Intentando establecer el último ID procesado a {message_id}.")
    if message_id > bot_config["last_processed_message_id"]:
        bot_config["last_processed_message_id"] = message_id
        log_action("ACTUALIZACIÓN ÚLTIMO ID", f"Último ID procesado actualizado a {message_id}.")
        save_config()
    else:
        log_action("ACTUALIZACIÓN ÚLTIMO ID", f"El nuevo ID {message_id} no es mayor que el actual {bot_config['last_processed_message_id']}. No se actualiza.")


async def process_message_for_forwarding(message):
    log_action("PROCESANDO MENSAJE", f"Iniciando procesamiento para mensaje ID: {message.id} del canal: {message.channel.name if not isinstance(message.channel, discord.DMChannel) else 'DM'}") # Updated logging
    current_last_processed_id = get_last_processed_id()
    
    if message.author == bot.user:
        log_action("PROCESANDO MENSAJE", f"Mensaje ID {message.id} es del propio bot. Ignorando.")
        return
    if message.id <= current_last_processed_id:
        log_action("PROCESANDO MENSAJE", f"Mensaje ID {message.id} ya fue procesado o es anterior. Ignorando.")
        return
    
    # Usar el ID del canal desde la configuración
    channel_anything_id = bot_config.get("channel_anything_id")
    if channel_anything_id is None:
        log_action("ADVERTENCIA", f"El ID del canal 'anything' no está configurado. No se procesarán los mensajes para reenvío. Mensaje ID: {message.id}")
        # Aún guardamos el ID para no reprocesar este mensaje si el canal se configura más tarde
        set_last_processed_id(message.id) 
        return

    # Si el mensaje es de un DM, no lo procesamos para reenvío
    if isinstance(message.channel, discord.DMChannel):
        log_action("PROCESANDO MENSAJE", f"Mensaje ID {message.id} es de un canal DM. No apto para reenvío. Ignorando.")
        set_last_processed_id(message.id) # Guarda el ID para no reprocesar
        return

    if message.channel.id != channel_anything_id:
        log_action("PROCESANDO MENSAJE", f"Mensaje ID {message.id} no es del canal 'anything' configurado. Guardando ID y terminando.")
        set_last_processed_id(message.id)
        return

    log_action("PROCESANDO MENSAJE", f"Mensaje ID {message.id} del canal {message.channel.name} apto para análisis de reenvío.")

    forward_content = []
    text_for_rules = ""
    total_gp = 0
    lvl = None

    if message.embeds:
        log_action("ANÁLISIS MENSAJE", f"Mensaje ID {message.id} contiene embeds. Procesando el primer embed.")
        embed = message.embeds[0]
        forward_content.append({"type": "embed", "data": embed})
        text_for_rules += (embed.title or "") + (embed.description or "")
        log_action("ANÁLISIS MENSAJE", f"Texto del embed extraído: '{text_for_rules[:50]}...'")

        if "has levelled" in text_for_rules.lower():
            m = re.search(r'to (\d+)', text_for_rules.lower())
            if m:
                lvl = int(m.group(1))
                log_action("DETECCIÓN DE DATOS", f"Nivel '{lvl}' detectado en embed del mensaje ID {message.id}.")

        for f in embed.fields:
            log_action("ANÁLISIS MENSAJE", f"Procesando campo de embed: '{f.name}' con valor '{f.value}'")
            if "total value" in (f.name or "").lower():
                value_text_lower = (f.value or "").lower()
                m = re.search(r'([\d,.]+)\s*([kmbgt])?', value_text_lower)
                if m:
                    v = float(m.group(1).replace(',', ''))
                    suf = m.group(2)
                    mult = {'k':1e3,'m':1e6,'b':1e9,'t':1e12}.get(suf, 1)
                    total_gp = int(v*mult)
                    log_action("DETECCIÓN DE DATOS", f"GP '{total_gp}' detectado en embed del mensaje ID {message.id}.")
                    break
                else:
                    log_action("ADVERTENCIA", f"No se pudo parsear valor de GP en campo '{f.name}': '{f.value}'")
    else:
        log_action("ANÁLISIS MENSAJE", f"Mensaje ID {message.id} no contiene embeds.")

    if message.attachments:
        log_action("ANÁLISIS MENSAJE", f"Mensaje ID {message.id} contiene adjuntos. Procesando...")
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                log_action("ANÁLISIS MENSAJE", f"Adjunto '{attachment.filename}' es una imagen. Preparando para reenvío.")
                forward_content.append({"type": "file", "data": await attachment.to_file()})
            else:
                log_action("ADVERTENCIA", f"Adjunto '{attachment.filename}' no es una imagen compatible. Ignorado.")
    else:
        log_action("ANÁLISIS MENSAJE", f"Mensaje ID {message.id} no contiene adjuntos.")

    if message.content:
        log_action("ANÁLISIS MENSAJE", f"Mensaje ID {message.id} contiene texto. Añadiendo a texto para reglas.")
        text_for_rules += message.content.lower()
        log_action("ANÁLISIS MENSAJE", f"Texto completo para reglas: '{text_for_rules[:100]}...'")

    if not forward_content and not text_for_rules:
        log_action("IGNORADO", f"Mensaje ID {message.id}: Sin contenido relevante (embeds, adjuntos, texto) para procesar reglas. Guardando ID y terminando.")
        set_last_processed_id(message.id)
        return

    log_action("APLICANDO REGLAS", f"Aplicando reglas de reenvío al mensaje ID {message.id}.")
    found_rule_match = False
    for rule in get_reenvios_config():
        log_action("EVALUANDO REGLA", f"Evaluando regla '{rule.get('name', 'sin nombre')}' para mensaje ID {message.id}.")
        kw = [k.lower() for k in rule.get("keywords", [])]
        min_gp = rule.get("min_value_gp", 0)
        specific_levels = rule.get("specific_levels", None)

        keyword_match = any(k in text_for_rules for k in kw)
        gp_met = total_gp >= min_gp
        
        log_action("EVALUANDO REGLA", f"Regla '{rule.get('name', 'sin nombre')}': Palabras clave ({kw}) = {keyword_match}, GP mínimo ({min_gp}) = {gp_met}, GP del mensaje = {total_gp}.")

        should_forward = keyword_match and gp_met

        if should_forward and specific_levels is not None:
            if lvl is not None:
                if lvl not in specific_levels:
                    log_action("EVALUANDO REGLA", f"Regla '{rule.get('name', 'sin nombre')}': Nivel {lvl} NO está en niveles específicos {specific_levels}. No se reenviará por esta regla.")
                    should_forward = False
                else:
                    log_action("EVALUANDO REGLA", f"Regla '{rule.get('name', 'sin nombre')}': Nivel {lvl} COINCIDE con niveles específicos {specific_levels}.")
            else:
                log_action("EVALUANDO REGLA", f"Regla '{rule.get('name', 'sin nombre')}': Se requieren niveles específicos pero no se detectó nivel en el mensaje. No se reenviará por esta regla.")
                should_forward = False

        if should_forward:
            found_rule_match = True
            channel_id_to_forward = rule["channel_id"]
            ch = bot.get_channel(channel_id_to_forward)
            if ch:
                log_action("REENVÍO INICIADO", f"Mensaje ID {message.id} coincide con regla '{rule['name']}'. Reenviando a canal ID {channel_id_to_forward} ({ch.name}).")
                try:
                    await asyncio.sleep(1) # Small delay to prevent rate limits

                    for item in forward_content:
                        if item["type"] == "embed":
                            await ch.send(embed=item["data"])
                            log_action("REENVÍO PASO", f"Embed reenviado a {ch.name}.")
                        elif item["type"] == "file":
                            await ch.send(file=item["data"])
                            log_action("REENVÍO PASO", f"Adjunto (imagen) reenviado a {ch.name}.")
                    
                    log_action("REENVÍO OK", f"Mensaje {message.id} reenviado exitosamente a {ch.name} por regla '{rule['name']}'.")
                except Exception as e:
                    log_action("ERROR", f"Al reenviar mensaje {message.id} a {ch.name} por regla '{rule['name']}'", exception_obj=e)
            else:
                log_action("ERROR", f"Canal de destino ID {channel_id_to_forward} para la regla '{rule['name']}' no encontrado. No se pudo reenviar el mensaje {message.id}.")
    
    if not found_rule_match:
        log_action("APLICANDO REGLAS", f"Mensaje ID {message.id}: No hubo coincidencias con ninguna regla de reenvío.")
        
    set_last_processed_id(message.id)
    log_action("PROCESAMIENTO MENSAJE", f"Finalizado el procesamiento para el mensaje ID {message.id}.")

@bot.event
async def on_ready():
    log_action("EVENTO BOT", f"Bot conectado como {bot.user} (ID: {bot.user.id}).")
    load_config() # Asegura que la configuración, incluyendo channel_anything_id, esté cargada
    try:
        log_action("COMANDOS SLASH", "Intentando sincronizar comandos slash.")
        await tree.sync()
        log_action("COMANDOS SLASH", "Comandos slash sincronizados exitosamente.")
    except Exception as e:
        log_action("ERROR", "Al sincronizar comandos slash", exception_obj=e)
    
    # Solo intentar procesar historial si el canal 'anything' está configurado
    if bot_config.get("channel_anything_id") is not None:
        await process_history_from_last_id()
    else:
        log_action("INICIO BOT", "El ID del canal 'anything' no está configurado. El procesamiento de historial no se iniciará hasta que se configure.")


async def process_history_from_last_id():
    log_action("HISTORIAL", "Iniciando procesamiento de historial de mensajes.")
    
    channel_anything_id = bot_config.get("channel_anything_id")
    if channel_anything_id is None:
        log_action("ERROR", "El ID del canal 'anything' no está configurado en bot_config. No se procesará el historial.")
        return

    ch = bot.get_channel(channel_anything_id)
    if not ch:
        log_action("ERROR", f"Canal con ID {channel_anything_id} (configurado como 'anything') no encontrado. No se procesará el historial.")
        return
    
    last_id = get_last_processed_id()
    log_action("HISTORIAL", f"Procesando historial en el canal '{ch.name}' (ID: {ch.id}) desde el último ID procesado: {last_id}.")
    
    try:
        message_count = 0
        # Fetch history from after the last processed ID, oldest first
        async for msg in ch.history(limit=None, after=discord.Object(last_id), oldest_first=True):
            log_action("HISTORIAL", f"Procesando mensaje de historial ID: {msg.id}.")
            await process_message_for_forwarding(msg)
            message_count += 1
        log_action("HISTORIAL", f"Procesamiento de historial completado. {message_count} mensajes procesados.")
    except Exception as e:
        log_action("ERROR", "Al procesar historial de mensajes", exception_obj=e)

@bot.event
async def on_message(message):
    channel_info = ""
    if isinstance(message.channel, discord.DMChannel):
        channel_info = f"DM con {message.channel.recipient}" # Use recipient for DM channels
    else:
        channel_info = f"canal '{message.channel.name}' (ID: {message.channel.id})"

    log_action("EVENTO BOT", f"Mensaje detectado en el {channel_info} por {message.author} (ID: {message.author.id}). Contenido: '{message.content[:50]}...'")
    await process_message_for_forwarding(message)
    await bot.process_commands(message) # Important: this line processes other bot commands starting with '!'

# ---- COMANDOS SLASH ----

@tree.command(name="price", description="Precio de un ítem OSRS.")
@app_commands.describe(item="Nombre del ítem.")
async def price(interaction: discord.Interaction, item: str):
    log_action("COMANDO SLASH: PRICE", f"Solicitud del precio de ítem '{item}' por el usuario {interaction.user.name} (ID: {interaction.user.id}).")
    await interaction.response.defer()
    try:
        log_action("API CALL: PRICE", "Realizando llamada a RuneScape Wiki API para 'mapping'.")
        mp_response = requests.get("https://prices.runescape.wiki/api/v1/osrs/mapping", headers={'User-Agent':'Discord Bot'})
        mp_response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        mp = mp_response.json()
        log_action("API CALL: PRICE", "Mapping data recibida.")

        d = next((i for i in mp if i["name"].lower()==item.lower()),None)
        if not d:
            log_action("COMANDO SLASH: PRICE", f"Ítem '{item}' no encontrado en el mapeo de la API.")
            await interaction.followup.send(f"❌ Ítem no encontrado: **{item}**")
            return
        
        pid = d["id"]
        log_action("API CALL: PRICE", f"Ítem '{item}' encontrado, ID: {pid}. Realizando llamada a RuneScape Wiki API para 'latest price'.")
        pd_response = requests.get(f"https://prices.runescape.wiki/api/v1/osrs/latest?id={pid}", headers={'User-Agent':'Discord Bot'})
        pd_response.raise_for_status()
        pd = pd_response.json()
        log_action("API CALL: PRICE", f"Datos de precio recibidos para ID: {pid}.")

        dat = pd["data"].get(str(pid),{})
        h = dat.get("high","N/A")
        l = dat.get("low","N/A")
        fmt = lambda x: f"{x:,}" if isinstance(x,int) else x
        hi,lo = fmt(h),fmt(l)
        
        thumb = f"https://oldschool.runescape.wiki/images/{d['name'].replace(' ','_')}.png"
        log_action("COMANDO SLASH: PRICE", f"Preparando embed para '{d['name']}'. Precio alto: {hi}, Precio bajo: {lo}.")

        emb = discord.Embed(title=f"💰 {d['name']}",
                            description=f"🔼 **{hi} gp**\n🔽 **{lo} gp**",
                            color=discord.Color.green())
        emb.set_thumbnail(url=thumb)
        emb.set_footer(text=f"Última actualización: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        await interaction.followup.send(embed=emb)
        log_action("COMANDO SLASH: PRICE", f"Embed de precio para '{item}' enviado exitosamente.")
    except requests.exceptions.RequestException as req_e:
        log_action("ERROR", f"Error de red/API al obtener precio para '{item}'", exception_obj=req_e)
        await interaction.followup.send("❌ Error de comunicación con la API. Por favor, inténtalo de nuevo más tarde.")
    except Exception as e:
        log_action("ERROR", "Al obtener precio del ítem", exception_obj=e)
        await interaction.followup.send("❌ Error al obtener el precio del ítem. Por favor, inténtalo de nuevo más tarde.")

@tree.command(name="alias", description="Añade un alias para un boss o evento.")
@app_commands.describe(original="Nombre original (ej: 'Vorkath')", alias="Alias que quieres usar (ej: 'Vork')")
async def add_alias(interaction: discord.Interaction, original: str, alias: str):
    log_action("COMANDO SLASH: ALIAS", f"Solicitud para añadir alias: '{alias}' para '{original}' por {interaction.user.name}.")
    await interaction.response.defer()
    alias_lower = alias.lower()

    current_alias_map = get_alias_map()
    if alias_lower in current_alias_map:
        log_action("COMANDO SLASH: ALIAS", f"Alias '{alias}' ya existe para '{current_alias_map[alias_lower]}'. No se puede añadir.")
        await interaction.followup.send(f"❌ El alias `{alias}` ya existe para `{current_alias_map[alias_lower]}`. Si quieres cambiarlo, primero bórralo con `/delalias`.")
        return
    
    current_alias_map[alias_lower] = original
    set_alias_map(current_alias_map)
    log_action("COMANDO SLASH: ALIAS", f"Alias '{alias}' => '{original}' agregado exitosamente.")
    await interaction.followup.send(f"✅ Alias `{alias}` agregado para `{original}`.")

@tree.command(name="delalias", description="Borra un alias existente.")
@app_commands.describe(alias="El alias a borrar")
async def delete_alias(interaction: discord.Interaction, alias: str):
    log_action("COMANDO SLASH: DELALIAS", f"Solicitud para borrar alias: '{alias}' por {interaction.user.name}.")
    await interaction.response.defer()
    alias_lower = alias.lower()

    current_alias_map = get_alias_map()
    if alias_lower in current_alias_map:
        original_name = current_alias_map.pop(alias_lower)
        set_alias_map(current_alias_map)
        log_action("COMANDO SLASH: DELALIAS", f"Alias '{alias}' (apuntaba a '{original_name}') borrado exitosamente.")
        await interaction.followup.send(f"✅ Alias `{alias}` borrado. Antes apuntaba a `{original_name}`.")
    else:
        log_action("COMANDO SLASH: DELALIAS", f"Intento de borrar alias '{alias}' que no existe.")
        await interaction.followup.send(f"❌ El alias `{alias}` no existe.")

@tree.command(name="listaliases", description="Muestra todos los alias configurados.")
async def list_aliases(interaction: discord.Interaction):
    log_action("COMANDO SLASH: LISTALIASES", f"Solicitud para listar alias por {interaction.user.name}.")
    await interaction.response.defer()
    current_alias_map = get_alias_map()
    if not current_alias_map:
        log_action("COMANDO SLASH: LISTALIASES", "No hay alias configurados para mostrar.")
        await interaction.followup.send("No hay alias configurados actualmente.")
        return
    
    aliases_str = "\n".join([f"**{alias}** -> {original}" for alias, original in current_alias_map.items()])
    emb = discord.Embed(
        title="📝 Alias Configurados",
        description=aliases_str,
        color=discord.Color.blue()
    )
    log_action("COMANDO SLASH: LISTALIASES", f"Enviando lista de {len(current_alias_map)} alias configurados.")
    await interaction.followup.send(embed=emb)

@tree.command(name="lvls", description="Niveles de una cuenta OSRS.")
@app_commands.describe(username="Nombre exacto del jugador OSRS.")
async def lvls(interaction: discord.Interaction, username: str):
    log_action("COMANDO SLASH: LVLS", f"Solicitud de niveles para usuario '{username}' por {interaction.user.name}.")
    await interaction.response.defer()
    try:
        log_action("API CALL: LVLS", f"Realizando llamada a Hiscores OSRS para usuario '{username}'.")
        r = requests.get(f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={username.replace(' ','+')}")
        
        if r.status_code != 200:
            log_action("COMANDO SLASH: LVLS", f"Perfil '{username}' no encontrado (HTTP Status: {r.status_code}).")
            await interaction.followup.send(f"❌ Perfil no encontrado: **{username}**. Asegúrate de escribir el nombre exacto.")
            return
        
        lines = r.text.splitlines()
        skills = ["Overall","Attack","Defence","Strength","Hitpoints","Ranged",
                    "Prayer","Magic","Cooking","Woodcutting","Fletching","Fishing",
                    "Firemaking","Crafting","Smithing","Mining","Herblore","Agility",
                    "Thieving","Slayer","Farming","Runecraft","Hunter","Construction"]
        
        emb = discord.Embed(title=f"📊 Niveles de {username}", color=discord.Color.gold())
        emb.set_footer(text=f"Última actualización: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        
        for i,sk in enumerate(skills):
            lvl = lines[i].split(",")[1] if i < len(lines) else "N/A"
            emb.add_field(name=sk, value=lvl, inline=True)
            log_action("API CALL: LVLS", f"Añadiendo nivel {lvl} para habilidad {sk}.")
        
        await interaction.followup.send(embed=emb)
        log_action("COMANDO SLASH: LVLS", f"Embed de niveles para '{username}' enviado exitosamente.")
    except requests.exceptions.RequestException as req_e:
        log_action("ERROR", f"Error de red/API al obtener niveles para '{username}'", exception_obj=req_e)
        await interaction.followup.send("❌ Error de comunicación con la API. Por favor, inténtalo de nuevo más tarde.")
    except Exception as e:
        log_action("ERROR", "Al obtener niveles de jugador", exception_obj=e)
        await interaction.followup.send("❌ Error al obtener los niveles. Por favor, inténtalo de nuevo más tarde.")

@tree.command(name="kc", description="Kills de un boss OSRS.")
@app_commands.describe(username="Cuenta exacta", boss="Nombre o alias del boss.")
async def kc(interaction: discord.Interaction, username: str, boss: str):
    log_action("COMANDO SLASH: KC", f"Solicitud de KC para usuario '{username}', boss: '{boss}' por {interaction.user.name}.")
    await interaction.response.defer()

    boss_input = boss.lower()
    boss_name_to_search = get_alias_map().get(boss_input, boss)
    log_action("COMANDO SLASH: KC", f"Nombre del boss a buscar (considerando alias): '{boss_name_to_search}'.")

    player_url_friendly = username.replace(' ','+')
    
    # --- Lógica de caché ---
    cached_data = player_hiscores_cache.get(player_url_friendly)
    soup = None
    if cached_data and (time.time() - cached_data['timestamp']) < CACHE_EXPIRY_SECONDS:
        soup = cached_data['soup']
        log_action("CACHÉ KC", f"Usando datos de caché para '{username}'.")
    else:
        try:
            log_action("API CALL: KC", f"Realizando llamada a Hiscores OSRS para perfil personal de '{username}'.")
            r = requests.get(
                f"https://secure.runescape.com/m=hiscore_oldschool/hiscorepersonal?user1={player_url_friendly}",
                headers={'User-Agent':'Discord Bot'}, timeout=10
            )
            r.raise_for_status()
            log_action("API CALL: KC", "Perfil personal recibido. Parseando con BeautifulSoup.")
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Guardar en caché
            player_hiscores_cache[player_url_friendly] = {
                'soup': soup,
                'timestamp': time.time()
            }
            log_action("CACHÉ KC", f"Datos para '{username}' guardados en caché.")

        except requests.exceptions.RequestException as req_e:
            log_action("ERROR", f"Error de red/API al obtener KC para '{username}'", exception_obj=req_e)
            await interaction.followup.send("❌ Error de comunicación con la API de RuneScape Hiscores. Por favor, inténtalo de nuevo más tarde.")
            return
        except Exception as e:
            log_action("ERROR", "Al obtener KC", exception_obj=e)
            await interaction.followup.send("❌ Error al obtener KC. Por favor, inténtalo de nuevo más tarde.")
            return

    if not soup: # Si por alguna razón soup es None después del intento de caché/fetch
        log_action("ERROR", f"No se pudo obtener el HTML para {username} después del intento de caché y fetch.")
        await interaction.followup.send("❌ No se pudo procesar la solicitud. Por favor, inténtalo de nuevo más tarde.")
        return

    best, ratio = None, 0
    
    for row in soup.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 4:
            continue
        
        tag = cols[1].find('a')
        kc_td = cols[3] 
        
        if not tag or not kc_td:
            continue
        
        name = tag.text.strip()
        kc_val = kc_td.text.strip()
        sim = fuzz.ratio(boss_name_to_search.lower(), name.lower())
        log_action("SIMILITUD KC", f"Comparando '{boss_name_to_search}' con '{name}'. Similitud: {sim}%.")
        
        if sim > ratio:
            best, ratio = {
                'name': name,
                'kc': kc_val,
                'img': cols[0].find('img')['src'] if cols[0].find('img') else None
            }, sim
            if sim == 100:
                log_action("SIMILITUD KC", f"Coincidencia exacta encontrada para '{name}'. Deteniendo búsqueda.")
                break

    if not best or ratio < 70:
        log_action("COMANDO SLASH: KC", f"No se encontró el boss '{boss}' (o su alias) para '{username}' con suficiente similitud (mejor ratio: {ratio}%).")
        await interaction.followup.send(f"❌ No se encontró el boss '{boss}' para {username}. Intenta un nombre más exacto o verifica el perfil.")
        return

    log_action("COMANDO SLASH: KC", f"Boss '{best['name']}' encontrado para '{username}' con {best['kc']} kills. Similitud: {ratio}%.")
    emb = discord.Embed(
        title=f"☠ KC de {username}",
        description=f"**{best['name']}**\n🔢 {best['kc']} kills",
        color=discord.Color.red()
    )
    if best['img']:
        emb.set_thumbnail(url=best['img'])
    emb.set_footer(text=f"Última actualización: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    await interaction.followup.send(embed=emb)
    log_action("COMANDO SLASH: KC", f"Embed de KC para '{username}' enviado exitosamente.")

@tree.command(name="establecer_canal_anything", description="Establece el ID del canal 'anything' para procesar mensajes.")
@app_commands.describe(id_del_canal="ID numérico del canal de Discord.")
@app_commands.default_permissions(manage_guild=True) # Requiere permisos de "Gestionar Servidor"
async def establecer_canal_anything(interaction: discord.Interaction, id_del_canal: str):
    log_action("COMANDO SLASH: ESTABLECER_CANAL_ANYTHING", f"Solicitud para establecer canal 'anything' a {id_del_canal} por {interaction.user.name}.")
    await interaction.response.defer(ephemeral=True) # Respuesta efímera

    try:
        channel_id_int = int(id_del_canal)
        target_channel = bot.get_channel(channel_id_int)
        if not target_channel:
            await interaction.followup.send(f"❌ No pude encontrar un canal con el ID `{id_del_canal}`. Asegúrate de que el bot tenga acceso a ese canal.", ephemeral=True)
            log_action("COMANDO SLASH: ESTABLECER_CANAL_ANYTHING", f"No se encontró el canal con ID {id_del_canal}.")
            return
        
        bot_config["channel_anything_id"] = channel_id_int
        save_config()
        log_action("COMANDO SLASH: ESTABLECER_CANAL_ANYTHING", f"Canal 'anything' establecido a ID {channel_id_int} ({target_channel.name}).")
        await interaction.followup.send(f"✅ El canal 'anything' ha sido establecido a **#{target_channel.name}** (ID: `{channel_id_int}`).", ephemeral=True)

    except ValueError:
        log_action("ERROR", f"ID de canal inválido proporcionado: '{id_del_canal}'.")
        await interaction.followup.send("❌ Por favor, proporciona un ID de canal numérico válido.", ephemeral=True)
    except Exception as e:
        log_action("ERROR", "Al establecer el canal 'anything'", exception_obj=e)
        await interaction.followup.send("❌ Ocurrió un error al intentar establecer el canal. Por favor, inténtalo de nuevo.", ephemeral=True)

@tree.command(name="obtener_canal_anything", description="Muestra el ID actual del canal 'anything'.")
async def obtener_canal_anything(interaction: discord.Interaction):
    log_action("COMANDO SLASH: OBTENER_CANAL_ANYTHING", f"Solicitud para obtener canal 'anything' por {interaction.user.name}.")
    await interaction.response.defer(ephemeral=True) # Respuesta efímera
    
    current_id = bot_config.get("channel_anything_id")
    if current_id:
        channel = bot.get_channel(current_id)
        if channel:
            await interaction.followup.send(f"➡️ El canal 'anything' actual es **#{channel.name}** (ID: `{current_id}`).", ephemeral=True)
            log_action("COMANDO SLASH: OBTENER_CANAL_ANYTHING", f"Canal 'anything' actual: {channel.name} ({current_id}).")
        else:
            await interaction.followup.send(f"➡️ El canal 'anything' actual es el ID `{current_id}`, pero no pude encontrar ese canal (podría haber sido eliminado o el bot no tiene acceso).", ephemeral=True)
            log_action("COMANDO SLASH: OBTENER_CANAL_ANYTHING", f"Canal 'anything' actual es ID {current_id}, pero no encontrado.")
    else:
        await interaction.followup.send("➡️ El canal 'anything' aún no ha sido configurado. Usa `/establecer_canal_anything` para configurarlo.", ephemeral=True)
        log_action("COMANDO SLASH: OBTENER_CANAL_ANYTHING", "Canal 'anything' no configurado.")


if __name__ == "__main__":
    log_action("INICIO DEL SCRIPT", "Verificando variables de entorno y comenzando el bot.")
    if not TOKEN:
        log_action("ERROR FATAL", "La variable de entorno DISCORD_TOKEN no está definida. Saliendo.")
        sys.exit(1)
    
    try:
        log_action("BOT RUN", "Llamando a bot.run(TOKEN).")
        bot.run(TOKEN)
    except discord.LoginFailure as lf_e:
        log_action("ERROR FATAL", "Falló el inicio de sesión del bot. Token inválido o permisos incorrectos.", exception_obj=lf_e)
        sys.exit(1)
    except Exception as e:
        log_action("ERROR FATAL", "Error inesperado al iniciar el bot.", exception_obj=e)
        sys.exit(1)