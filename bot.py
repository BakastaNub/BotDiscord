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

# Ensure the script changes directory if running as a PyInstaller frozen executable
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

# Load environment variables from .env file
load_dotenv()

# --- Configuration Variables ---
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ANYTHING_ID = int(os.getenv("CHANNEL_ANYTHING_ID"))
REENVIOS_CONFIG_FILE = "reenvios.json"
LAST_PROCESSED_ID_FILE = "ultimo_reenvio.txt"

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True   # Required to read message content
intents.messages = True          # Required for message events

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # Command tree for slash commands

# --- Global Variables for Configuration and State ---
reenvios_config = []  # Stores forwarding rules
last_processed_message_id = 0  # Stores the ID of the last message processed

# --- Helper Functions ---

def log_action(action, message=None, error=None):
    """
    Logs actions, messages, or errors with a timestamp to the console.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if error:
        print(f"❌ [{timestamp}] ERROR en {action}: {error}")
    elif message:
        print(f"🔹 [{timestamp}] {action}: {message}")
    else:
        print(f"📌 [{timestamp}] {action}")

def load_reenvios_config():
    """
    Loads forwarding rules from the reenvios.json file.
    Initializes an empty list if the file doesn't exist or an error occurs.
    """
    global reenvios_config
    try:
        if not os.path.exists(REENVIOS_CONFIG_FILE):
            log_action("ADVERTENCIA", f"El archivo '{REENVIOS_CONFIG_FILE}' no existe. Se creará uno nuevo.")
            reenvios_config = []
            return
        with open(REENVIOS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            reenvios_config = json.load(f)
        for rule in reenvios_config:
            log_action("REGLA CARGADA", f"'{rule.get('name', 'Nombre no disponible')}'")
    except json.JSONDecodeError as e:
        log_action("ERROR", f"Error al decodificar JSON en '{REENVIOS_CONFIG_FILE}': {e}", error=True)
        reenvios_config = []
    except Exception as e:
        log_action("ERROR", f"Error al cargar configuración de reenvíos: {e}", error=True)
        reenvios_config = []

def save_reenvios_config():
    """
    Saves the current forwarding rules to the reenvios.json file.
    """
    try:
        with open(REENVIOS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(reenvios_config, f, indent=2)
        log_action("CONFIGURACIÓN GUARDADA", f"Reglas guardadas en '{REENVIOS_CONFIG_FILE}'")
    except Exception as e:
        log_action("ERROR", f"Error al guardar configuración de reenvíos: {e}", error=True)

def load_last_processed_id():
    """
    Loads the ID of the last processed message from a file.
    Initializes to 0 if the file doesn't exist or an error occurs.
    """
    global last_processed_message_id
    try:
        if os.path.exists(LAST_PROCESSED_ID_FILE):
            with open(LAST_PROCESSED_ID_FILE, 'r') as f:
                last_processed_message_id = int(f.read().strip())
            log_action("ÚLTIMO ID PROCESADO", f"Cargado: {last_processed_message_id}")
        else:
            with open(LAST_PROCESSED_ID_FILE, 'w') as f:
                f.write("0")
            last_processed_message_id = 0
            log_action("ÚLTIMO ID PROCESADO", "Archivo no encontrado, inicializado a 0.")
    except ValueError:
        log_action("ERROR", f"Contenido inválido en '{LAST_PROCESSED_ID_FILE}'. Inicializando a 0.", error=True)
        last_processed_message_id = 0
    except Exception as e:
        log_action("ERROR", f"Error al cargar último ID procesado: {e}", error=True)
        last_processed_message_id = 0

def save_last_processed_id(message_id):
    """
    Saves the ID of the last processed message to a file,
    but only if the new ID is greater than the current one.
    """
    global last_processed_message_id
    if message_id > last_processed_message_id:
        last_processed_message_id = message_id
        try:
            with open(LAST_PROCESSED_ID_FILE, 'w') as f:
                f.write(str(message_id))
            # log_action("ID ACTUALIZADO", f"Último ID procesado: {message_id}") # Uncomment for verbose logging
        except Exception as e:
            log_action("ERROR", f"Error al guardar el último ID procesado ({message_id}): {e}", error=True)

async def process_message_for_forwarding(message):
    """
    Processes a given message to check if it matches any forwarding rules
    and forwards it to the appropriate channels.
    """
    if message.author == bot.user:
        return  # Ignore messages from the bot itself
    if message.id <= last_processed_message_id:
        return  # Skip already processed messages
    if message.channel.id != CHANNEL_ANYTHING_ID:
        save_last_processed_id(message.id) # Save ID even if not the target channel
        return  # Only process messages from the designated channel

    log_action("MENSAJE RECIBIDO", f"ID: {message.id} | Canal: {message.channel.name}")

    if not message.embeds:
        save_last_processed_id(message.id)
        return # Skip messages without embeds

    embed = message.embeds[0] # Consider only the first embed
    embed_text = ""
    if embed.title:
        embed_text += embed.title.lower()
    if embed.description:
        embed_text += embed.description.lower()

    total_value_gp = 0
    extracted_level = None

    # Extract level if "has levelled" is in the embed text
    if "has levelled" in embed_text:
        level_match = re.search(r'has levelled .+ to (\d+)', embed_text, re.IGNORECASE)
        if level_match:
            try:
                extracted_level = int(level_match.group(1))
            except ValueError:
                log_action("ADVERTENCIA", f"No se pudo extraer el nivel de '{level_match.group(1)}'.")
                pass

    # Extract total value from embed fields
    for field in embed.fields:
        field_name = (field.name or "").lower()
        field_value = (field.value or "").lower()
        if "total value" in field_name:
            # Regex to match numbers with optional thousands commas, suffixes (k, m, b, t), and "gp"
            match = re.search(r'([\d,.]+)\s*([kmbgt])?\s*(gp)?', field_value, re.IGNORECASE)
            if match:
                try:
                    numeric_part = match.group(1).replace(',', '')
                    value = float(numeric_part)
                    suffix = (match.group(2) or '').lower()

                    if suffix == 'k':
                        value *= 1_000
                    elif suffix == 'm':
                        value *= 1_000_000
                    elif suffix == 'b':
                        value *= 1_000_000_000
                    elif suffix == 't':
                        value *= 1_000_000_000_000
                    total_value_gp = int(value)
                except ValueError:
                    log_action("ADVERTENCIA", f"No se pudo parsear el valor GP de '{field_value}'.")
                    pass
        embed_text += field_name + field_value # Add field content to embed_text for keyword matching

    forwarded_to_any_channel = False
    for rule in reenvios_config:
        dest_channel_id = rule.get("channel_id")
        keywords = [kw.lower() for kw in rule.get("keywords", [])]
        min_value = rule.get("min_value_gp", 0)
        rule_name = rule.get("name", "Regla sin nombre")
        specific_levels = rule.get("specific_levels") # This is a new optional field

        if dest_channel_id is None:
            log_action("ADVERTENCIA", f"Regla '{rule_name}' no tiene 'channel_id' configurado. Saltando.")
            continue

        keywords_match = any(keyword in embed_text for keyword in keywords)
        value_match = (total_value_gp >= min_value)

        level_condition_met = True
        if specific_levels is not None:
            # If specific_levels is defined, check if extracted_level is one of them
            if extracted_level is None or extracted_level not in specific_levels:
                level_condition_met = False

        if keywords_match and value_match and level_condition_met:
            dest_channel = bot.get_channel(dest_channel_id)
            if dest_channel:
                log_action("REENVIANDO", f"Mensaje {message.id} a '{dest_channel.name}' (Regla: '{rule_name}')")
                try:
                    await asyncio.sleep(1)  # Small delay to avoid rate limits
                    await dest_channel.send(embed=embed)
                    forwarded_to_any_channel = True
                except discord.HTTPException as e:
                    log_action("ERROR", f"No se pudo reenviar mensaje a '{dest_channel.name}': {e}", error=True)
                except Exception as e:
                    log_action("ERROR", f"Error inesperado al reenviar a '{dest_channel.name}': {e}", error=True)
            else:
                log_action("ADVERTENCIA", f"Canal de destino con ID {dest_channel_id} para regla '{rule_name}' no encontrado.")
    
    # Always save the last processed ID after trying to process the message
    save_last_processed_id(message.id)

# --- Slash Commands ---

@tree.command(name="nueva_regla", description="Agregar una nueva regla de reenvío")
@app_commands.describe(
    name="Nombre único para la regla",
    channel_id="ID del canal de destino",
    keywords="Palabras clave separadas por coma (ej: 'loot, drop, reward')",
    min_value_gp="Valor mínimo en GP (opcional, por defecto 0)",
    specific_levels="Niveles específicos separados por coma (ej: '99,120', opcional)"
)
async def nueva_regla(interaction: discord.Interaction, name: str, channel_id: int, keywords: str, min_value_gp: int = 0, specific_levels: str = None):
    """Adds a new forwarding rule."""
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()]
    levels_list = None
    if specific_levels:
        try:
            levels_list = [int(lvl.strip()) for lvl in specific_levels.split(',') if lvl.strip()]
        except ValueError:
            await interaction.response.send_message("❌ Formato de niveles inválido. Usa números separados por coma.", ephemeral=True)
            return

    # Check for existing rule with the same name or channel ID
    for rule in reenvios_config:
        if rule["name"].lower() == name.lower():
            await interaction.response.send_message("❌ Ya existe una regla con ese nombre.", ephemeral=True)
            return
        if rule["channel_id"] == channel_id and any(kw in rule["keywords"] for kw in keywords_list):
            await interaction.response.send_message("❌ Ya existe una regla con ese canal y palabras clave similares.", ephemeral=True)
            return

    new_rule = {
        "name": name,
        "channel_id": channel_id,
        "keywords": keywords_list,
        "min_value_gp": min_value_gp
    }
    if levels_list is not None:
        new_rule["specific_levels"] = levels_list

    reenvios_config.append(new_rule)
    save_reenvios_config()
    log_action("REGLA AÑADIDA", f"'{name}'")
    await interaction.response.send_message(f"✅ Regla '{name}' añadida correctamente.", ephemeral=True)

@tree.command(name="eliminar_regla", description="Eliminar una regla de reenvío por nombre")
@app_commands.describe(name="Nombre de la regla a eliminar")
async def eliminar_regla(interaction: discord.Interaction, name: str):
    """Removes a forwarding rule by its name."""
    global reenvios_config
    initial_len = len(reenvios_config)
    reenvios_config = [rule for rule in reenvios_config if rule["name"].lower() != name.lower()]
    if len(reenvios_config) < initial_len:
        save_reenvios_config()
        log_action("REGLA ELIMINADA", f"'{name}'")
        await interaction.response.send_message(f"✅ Regla '{name}' eliminada correctamente.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No se encontró ninguna regla con el nombre '{name}'.", ephemeral=True)

@tree.command(name="ver_reglas", description="Listar todas las reglas de reenvío configuradas")
async def ver_reglas(interaction: discord.Interaction):
    """Lists all currently configured forwarding rules."""
    if not reenvios_config:
        await interaction.response.send_message("No hay reglas de reenvío configuradas.", ephemeral=True)
        return

    embed = discord.Embed(title="📜 Reglas de Reenvío Configuradas", color=discord.Color.blue())
    for rule in reenvios_config:
        ch = bot.get_channel(rule['channel_id'])
        name = rule.get("name", "N/A")
        channel_name = f"#{ch.name}" if ch else f"ID: {rule['channel_id']} (Desconocido)"
        keywords = ", ".join(rule.get("keywords", [])) if rule.get("keywords") else "Ninguna"
        min_value = rule.get("min_value_gp", 0)
        levels = rule.get("specific_levels")
        levels_display = ", ".join(map(str, levels)) if levels else "Cualquiera"
        
        embed.add_field(
            name=f"Rule: {name}",
            value=(
                f"**Canal:** {channel_name}\n"
                f"**Keywords:** `{keywords}`\n"
                f"**Min GP:** `{min_value:,}`\n"
                f"**Niveles:** `{levels_display}`"
            ),
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="recargar_reglas", description="Recargar la configuración de reenvío desde el archivo")
async def recargar_reglas(interaction: discord.Interaction):
    """Reloads forwarding rules from the configuration file."""
    load_reenvios_config()
    await interaction.response.send_message("🔄 Configuración de reenvío recargada.", ephemeral=True)

# --- Bot Events ---

@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected to Discord.
    Loads configurations and processes any missed messages.
    """
    log_action("BOT INICIADO", f"Conectado como {bot.user}")
    load_reenvios_config()
    load_last_processed_id()
    await tree.sync() # Sync slash commands with Discord
    log_action("COMANDOS SINCRONIZADOS", "Slash commands are ready.")
    await process_history_from_last_id()
    log_action("HISTORIAL PROCESADO", "Se han procesado los mensajes pendientes desde el último ID.")


async def process_history_from_last_id():
    """
    Processes messages from the designated channel that were sent
    after the last recorded processed message ID.
    This helps in catching messages sent while the bot was offline.
    """
    channel = bot.get_channel(CHANNEL_ANYTHING_ID)
    if not channel:
        log_action("ERROR", f"El canal con ID {CHANNEL_ANYTHING_ID} no fue encontrado al procesar historial.", error=True)
        return

    log_action("PROCESANDO HISTORIAL", f"Desde ID: {last_processed_message_id}")
    try:
        # Fetch messages older than the last processed ID, ordered oldest first
        async for message in channel.history(limit=None, after=discord.Object(last_processed_message_id), oldest_first=True):
            await process_message_for_forwarding(message)
    except discord.Forbidden:
        log_action("ERROR", f"No tengo permisos para leer el historial en el canal con ID {CHANNEL_ANYTHING_ID}.", error=True)
    except discord.HTTPException as e:
        log_action("ERROR", f"Error HTTP al procesar historial: {e}", error=True)
    except Exception as e:
        log_action("ERROR", f"Error inesperado al procesar historial: {e}", error=True)

@bot.event
async def on_message(message):
    """
    Called every time a message is sent in any channel the bot can see.
    Processes the message for forwarding rules and then processes bot commands.
    """
    if message.author == bot.user:
        return # Ignore messages from the bot itself
    
    await process_message_for_forwarding(message)
    await bot.process_commands(message) # Important: allows regular bot commands to still work

# --- Bot Run ---
if __name__ == "__main__":
    if TOKEN is None:
        log_action("ERROR", "El token de Discord no está configurado. Asegúrate de tener DISCORD_TOKEN en tu archivo .env", error=True)
        sys.exit(1)
    if CHANNEL_ANYTHING_ID is None:
        log_action("ERROR", "El ID del canal 'anything' no está configurado. Asegúrate de tener CHANNEL_ANYTHING_ID en tu archivo .env", error=True)
        sys.exit(1)
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        log_action("ERROR", "Fallo de inicio de sesión. Verifica tu TOKEN de Discord.", error=True)
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log_action("ERROR", "Se requieren intents privilegiados. Asegúrate de que 'Message Content Intent' esté habilitado en el portal de desarrolladores de Discord para tu bot.", error=True)
        sys.exit(1)
    except Exception as e:
        log_action("ERROR", f"Ocurrió un error al ejecutar el bot: {e}", error=True)
        sys.exit(1)