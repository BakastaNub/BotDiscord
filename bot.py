import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import datetime
import re

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ANYTHING_ID = int(os.getenv("CHANNEL_ANYTHING_ID"))
CHANNEL_DROPS_ID = int(os.getenv("CHANNEL_DROPS_ID"))
CHANNEL_DEATHS_ID = int(os.getenv("CHANNEL_DEATHS_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

def log_action(action, message=None, error=None):
    """Función para registrar eventos en la consola con timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if error:
        print(f"❌ [{timestamp}] ERROR en {action}: {error}")
    elif message:
        print(f"🔹 [{timestamp}] {action}: {message}")
    else:
        print(f"📌 [{timestamp}] {action}")

async def process_message(message):
    # Evitar que el bot procese sus propios mensajes reenviados
    if message.author == bot.user:
        return

    log_action("INICIANDO PROCESO", f"Mensaje ID: {message.id}, Canal: {message.channel.name}, Autor: {message.author.display_name} (bot: {message.author.bot})")

    if message.channel.id != CHANNEL_ANYTHING_ID:
        log_action("MENSAJE IGNORADO", f"No es del canal 'anything'. Canal ID: {message.channel.id}")
        return

    try:
        if not message.embeds:
            log_action("MENSAJE IGNORADO", "No hay embeds en el mensaje.")
            return

        embed = message.embeds[0]
        log_action("EMBED DETECTADO", f"Título del embed: {embed.title if embed.title else 'N/A'}")

        dest_channel = None
        should_delete_original = False 
        
        embed_text = (embed.title or "").lower() + (embed.description or "").lower()
        
        total_value_gp = 0

        for field in embed.fields:
            field_name = (field.name or "").lower()
            field_value = (field.value or "").lower()

            if "total value" in field_name:
                match = re.search(r'(\d[\d,\.]*)', field_value)
                if match:
                    numeric_string = match.group(1).replace(',', '').replace('.', '')
                    try:
                        total_value_gp = int(numeric_string)
                        log_action("DEBUG", f"Valor total del embed detectado: {total_value_gp} gp")
                    except ValueError:
                        log_action("ERROR", f"No se pudo convertir '{numeric_string}' a un número para valor total.", error=True)
            
            embed_text += (field_name or "") + field_value


        if "player death" in embed_text or "has died" in embed_text:
            dest_channel = bot.get_channel(CHANNEL_DEATHS_ID)
            if dest_channel:
                log_action("MUERTE DETECTADA", f"Embed de {message.author} → #{dest_channel.name}")
            else:
                log_action("ERROR", f"No se encontró el canal de muertes con ID: {CHANNEL_DEATHS_ID}", error=True)
            should_delete_original = True 
            
        elif "loot drop" in embed_text or "has looted" in embed_text:
            should_delete_original = True 
            if total_value_gp >= 1_000_000:
                dest_channel = bot.get_channel(CHANNEL_DROPS_ID)
                if dest_channel:
                    log_action("DROP DETECTADO (Alto Valor)", f"Embed de {message.author} ({total_value_gp} gp) → #{dest_channel.name}")
                else:
                    log_action("ERROR", f"No se encontró el canal de drops con ID: {CHANNEL_DROPS_ID}", error=True)
            else:
                log_action("DROP IGNORADO", f"El valor del loot ({total_value_gp} gp) es menor a 1,000,000 gp. Solo se borrará el original.")
        else:
            log_action("EMBED NO RELEVANTE", "El embed no contiene palabras clave para muerte o drop.")


        # --- Lógica de reenvío ---
        if dest_channel: 
            await dest_channel.send(embed=embed)
            log_action("REENVÍO EXITOSO", f"Embed enviado a #{dest_channel.name}")
        
        # --- Lógica de borrado (siempre al final, basada en should_delete_original) ---
        if should_delete_original:
            try:
                await message.delete()
                log_action("MENSAJE BORRADO", f"Mensaje {message.id} eliminado de #{message.channel.name} (autor: {message.author})")
            except discord.errors.Forbidden:
                log_action("ERROR", "Falta el permiso 'Manage Messages' o el mensaje es muy antiguo para borrarlo.", error=True)
            except discord.HTTPException as e:
                log_action("ERROR", f"Error HTTP al intentar borrar el mensaje ID {message.id}: {e}", error=True)
            except Exception as e:
                log_action("ERROR", f"Error inesperado al borrar el mensaje ID {message.id}: {str(e)}", error=True)
        else:
            log_action("NO BORRADO", "El mensaje no era un embed de muerte/drop, o no se marcó para borrado.")


    except Exception as e:
        log_action("ERROR GENERAL", f"Error al procesar el mensaje {message.id}: {str(e)}", error=True)

@bot.event
async def on_ready():
    log_action("BOT INICIADO", f"Conectado como {bot.user}")
    # Descomentar la siguiente línea para que el bot revise y procese el historial completo
    # del canal 'anything' cada vez que se inicie.
    log_action("INICIANDO REVISIÓN DEL HISTORIAL EN EL ARRANQUE...")
    await process_entire_history(limit=None) # 'limit=None' significa todos los mensajes
    log_action("REVISIÓN DEL HISTORIAL EN EL ARRANQUE FINALIZADA.")

async def process_entire_history(limit=None):
    """
    Procesa mensajes antiguos. Útil para la primera vez o para resincronizar.
    ¡Cuidado al usarlo sin límite en canales muy activos!
    """
    channel = bot.get_channel(CHANNEL_ANYTHING_ID)
    if not channel:
        log_action("ERROR", f"No se encontró el canal 'anything' con ID: {CHANNEL_ANYTHING_ID}", error=True)
        return

    log_action("INICIANDO REVISIÓN", f"Escaneando historial de #{channel.name} (límite: {limit if limit else 'ninguno'})...")
    count = 0
    try:
        # Recorrer los mensajes desde el más antiguo al más nuevo
        async for message in channel.history(limit=limit, oldest_first=True):
            # No queremos que el bot procese sus propios mensajes que ya reenvió al iniciar.
            # Esto es clave para evitar re-procesar los mismos embeds que él mismo puso en los canales de destino.
            # Aunque ya tengas 'if message.author == bot.user: return' en process_message, es una doble seguridad aquí.
            if message.author == bot.user:
                continue 
            await process_message(message)
            count += 1
        log_action("REVISIÓN COMPLETADA", f"{count} mensajes procesados.")
    except Exception as e:
        log_action("ERROR", f"Error al procesar el historial del canal: {str(e)}", error=True)

@bot.event
async def on_message(message):
    # Evitar que el bot procese sus propios mensajes reenviados
    if message.author == bot.user:
        return
    await process_message(message)
    await bot.process_commands(message)

bot.run(TOKEN)