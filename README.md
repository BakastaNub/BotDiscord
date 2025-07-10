# Discord Message Forwarding Bot

Este bot permite reenviar mensajes con contenido embebido desde un canal de entrada hacia otros canales de Discord basándose en reglas configurables. Además, incluye utilidades para Old School RuneScape (OSRS) como consulta de precios, niveles, kills y gestión de alias para bosses/eventos.

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
pip install discord.py python-dotenv requests fuzzywuzzy beautifulsoup4
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
  }
]
```

> Si no deseas filtrar por niveles específicos, simplemente omite el campo `specific_levels` en la regla.

### `ultimo_reenvio.txt`

Contiene el ID del último mensaje procesado para evitar duplicados.

### `aliases.json`

Guarda los alias personalizados para bosses/eventos de OSRS.

---

## Comandos Disponibles

### Reglas de Reenvío

- **`/nueva_regla`**  
  Agrega una nueva regla de reenvío.  
  **Parámetros:**

  - `name`: nombre único de la regla.
  - `channel_id`: ID del canal de destino.
  - `keywords`: palabras clave separadas por coma.
  - `min_value_gp`: valor mínimo en GP (opcional, por defecto 0).
  - `specific_levels`: niveles específicos separados por coma (opcional, deja vacío si no aplica).

  **Ejemplo:**

  ```
  /nueva_regla name:Drops channel_id:123456789012345678 keywords:loot,drop min_value_gp:1000000
  ```

- **`/eliminar_regla`**  
  Elimina una regla de reenvío por nombre.  
  **Parámetro:**

  - `name`: nombre de la regla a eliminar.

- **`/ver_reglas`**  
  Muestra una lista de todas las reglas configuradas.

- **`/recargar_reglas`**  
  Recarga las reglas desde el archivo `reenvios.json`.

---

### Utilidades OSRS

- **`/price`**  
  Consulta el precio de un ítem de OSRS.  
  **Parámetro:**

  - `item`: nombre del ítem.  
    **Ejemplo:**

  ```
  /price item:Dragon scimitar
  ```

- **`/lvls`**  
  Muestra los niveles de una cuenta OSRS.  
  **Parámetro:**

  - `username`: nombre exacto del jugador.  
    **Ejemplo:**

  ```
  /lvls username:Zezima
  ```

- **`/kc`**  
  Muestra los kills de un boss para una cuenta OSRS.  
  **Parámetros:**
  - `username`: nombre exacto de la cuenta.
  - `boss`: nombre o alias del boss (ej: "Vorkath", "Vork").  
    **Ejemplo:**
  ```
  /kc username:Zezima boss:Vork
  ```

---

### Gestión de Alias

- **`/alias`**  
  Añade un alias para un boss o evento.  
  **Parámetros:**

  - `original`: nombre original (ej: "Vorkath").
  - `alias`: alias que quieres usar (ej: "Vork").  
    **Ejemplo:**

  ```
  /alias original:Vorkath alias:Vork
  ```

- **`/delalias`**  
  Borra un alias existente.  
  **Parámetro:**

  - `alias`: el alias a borrar.

- **`/listaliases`**  
  Muestra todos los alias configurados.

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
- Para activar el entorno virtual en Windows:
  ```bash
  .\venv\Scripts\activate
  ```
  Para desactivarlo:
  ```bash
  deactivate
  ```

---

## Futuras Mejoras

- Comando `/ver_regla name:<nombre>` para inspeccionar una regla específica.
- Interfaz web para editar reglas visualmente.

---
