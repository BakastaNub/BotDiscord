# Discord Message Forwarding Bot

Este bot permite reenviar mensajes con contenido embebido desde un canal de entrada (por ejemplo, "Anything") hacia otros canales de Discord basándose en reglas configurables. Utiliza comandos de barra (slash commands) para administrar dichas reglas.

---

## Requisitos

- Python 3.10+
- Token de bot de Discord
- Archivo `.env` con:
  ```env
  DISCORD_TOKEN=TU_TOKEN_DEL_BOT
  CHANNEL_ANYTHING_ID=ID_DEL_CANAL_DE_ENTRADA
  ```

Instala las dependencias:

```bash
pip install discord.py python-dotenv
```

---

## Archivos de Configuración

### `reenvios.json`

Contiene las reglas para reenviar mensajes. Ejemplo:

```json
[
  {
    "name": "Drops",
    "channel_id": 123456789012345678,
    "keywords": ["loot", "drop"],
    "min_value_gp": 1000000
  },
  {
    "name": "Muertes",
    "channel_id": 987654321098765432,
    "keywords": ["player death", "has died"],
    "min_value_gp": 0
  }
]
```

### `ultimo_reenvio.txt`

Contiene el ID del último mensaje procesado para evitar duplicados.

---

## Comandos Disponibles

### `/add_forward_rule`

Agrega una nueva regla de reenvío.

**Parámetros:**

- `name`: nombre único de la regla.
- `channel_id`: ID del canal de destino.
- `min_value_gp`: valor mínimo en GP (oro).
- `keywords`: lista de palabras clave separadas por comas.

**Ejemplo:**

```
/add_forward_rule name:Drops channel_id:123456789012345678 min_value_gp:1000000 keywords:loot,drop,has looted
```

---

### `/list_forward_rules`

Muestra una lista de todas las reglas configuradas, incluyendo:

- Nombre
- Canal de destino
- Palabras clave
- Valor mínimo
- Niveles específicos (si aplica)

---

### `/reload_forward_config`

Recarga las reglas desde el archivo `reenvios.json`. Útil si modificas el archivo manualmente.

---

## Proceso de Reenvío

El bot detecta mensajes nuevos en el canal configurado como fuente (`CHANNEL_ANYTHING_ID`) y verifica si:

- El mensaje contiene un embed válido.
- Coincide con alguna palabra clave definida en una regla.
- Cumple con el valor mínimo especificado.
- Cumple con niveles específicos si están definidos.

Si todos los criterios se cumplen, el mensaje se reenvía al canal de destino.

---

## Notas

- Los comandos son visibles únicamente para usuarios con acceso al bot.
- El bot ignora sus propios mensajes y solo procesa mensajes embebidos.
- Se recomienda usar `ephemeral=True` para que las respuestas a comandos sean visibles solo al usuario que los ejecuta.

---

## Futuras Mejoras

- Comando `/view_forward_rule name:<nombre>` para inspeccionar una regla específica.
- Interfaz web para editar reglas visualmente.

---

## Licencia

MIT
