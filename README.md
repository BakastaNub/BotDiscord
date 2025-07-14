# Discord Message Forwarding Bot + OSRS Utilities

Este bot para Discord reenvía automáticamente ciertos mensajes desde un canal de entrada a canales de destino según reglas configuradas. Además, ofrece funcionalidades útiles para jugadores de **Old School RuneScape (OSRS)** como consulta de precios, niveles, kills y alias personalizables para bosses.

---

## 🛠 Requisitos

- Python 3.10 o superior
- Bot de Discord con token válido
- Archivo `.env` en la raíz con:

```env
DISCORD_TOKEN=TU_TOKEN_DEL_BOT
```

Instala las dependencias necesarias con:

```bash
pip install -r requirements.txt
```

Si no tienes `requirements.txt`, puedes instalar directamente:

```bash
pip install discord.py python-dotenv requests fuzzywuzzy beautifulsoup4
```

---

## ⚙️ Configuración automática

Al primer inicio, el bot crea automáticamente:

- `config.json`: contiene reglas de reenvío, alias, canal fuente y último mensaje procesado.
- `bot_activity.log`: archivo de log con actividad del bot.

Si existen los archivos antiguos `reenvios.json`, `aliases.json` o `ultimo_reenvio.txt`, el bot los migrará automáticamente a `config.json`.

---

## 📡 Proceso de Reenvío

El bot monitorea el canal configurado como “anything” y:

- Extrae contenido relevante de mensajes (texto, embed, adjuntos).
- Aplica reglas configuradas:
  - Palabras clave (`keywords`)
  - Valor mínimo en GP (`min_value_gp`)
  - Niveles específicos (`specific_levels`, opcional)

Si se cumplen los criterios, reenvía el mensaje al canal de destino.

---

## 🧾 Comandos Slash Disponibles

### 🔁 Reenvío de mensajes

- `/establecer_canal_anything id_del_canal:<ID>`  
  Define el canal donde se detectarán los mensajes a reenviar.  
  _Requiere permisos de “Gestionar servidor”._

- `/obtener_canal_anything`  
  Muestra el canal actualmente configurado como fuente.

### 📊 Utilidades OSRS

- `/price item:<nombre>`  
  Consulta precios altos y bajos de un ítem.

- `/lvls username:<nombre>`  
  Muestra los niveles de habilidades de un jugador.

- `/kc username:<nombre> boss:<nombre o alias>`  
  Muestra las kills de un boss en el perfil del jugador.  
  Admite alias personalizados definidos con `/alias`.

### 🧩 Gestión de Alias

- `/alias original:<nombre> alias:<alias>`  
  Crea un alias para bosses o eventos.

- `/delalias alias:<alias>`  
  Elimina un alias existente.

- `/listaliases`  
  Muestra todos los alias actuales.

---

## 🔧 Estructura del archivo config.json

Ejemplo de configuración:

```json
{
  "reenvios_config": [
    {
      "name": "Drops caros",
      "channel_id": 123456789012345678,
      "keywords": ["drop", "loot"],
      "min_value_gp": 1000000,
      "specific_levels": [99]
    }
  ],
  "last_processed_message_id": 0,
  "alias_map": {
    "vork": "Vorkath",
    "zammy": "K'ril Tsutsaroth"
  },
  "channel_anything_id": 987654321098765432
}
```

> Si no deseas filtrar por niveles específicos, simplemente omite el campo `specific_levels` en la regla.

---

## 🧪 Consideraciones

- El bot ignora sus propios mensajes.
- Los mensajes DMs no se procesan.
- Los comandos son slash (`/`), visibles solo para quienes tengan acceso al bot.
- Las respuestas a comandos como `/establecer_canal_anything` son efímeras (solo visibles para el autor).

---

## 🗂 Archivos Generados

- `config.json`: configuración persistente del bot.
- `bot_activity.log`: log detallado de actividad y errores.
- `.env`: almacena el token de Discord.

---

## ✨ Mejoras futuras

- Comando `/ver_regla` para mostrar una regla específica.
- Interfaz web para administrar alias y reglas.
- Exportar configuración en JSON desde Discord.
