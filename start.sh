#!/bin/bash

# Asegúrate de que la carpeta para el disco persistente exista
mkdir -p /opt/render/project/src/data

# Copia config.json si existe en el disco persistente, si no existe en el disco persistente,
# se creará uno nuevo por tu script Python.
# Si el archivo NO existe en el disco persistente, Render montará una copia vacía,
# por lo que el mkdir -p es clave.
# Aquí asumimos que tu bot guardará config.json directamente en la raíz de tu app,
# y esa raíz es lo que se mapeará al disco persistente.
# Si estás usando la ruta /data en el disco persistente:
# cp -n /opt/render/project/src/data/config.json ./config.json 2>/dev/null || true
# cp -n /opt/render/project/src/data/bot_activity.log ./bot_activity.log 2>/dev/null || true

# Ya que tu setup_required_files() crea los archivos, y resource_path()
# apunta a la ruta absoluta, la forma más sencilla de manejar el disco persistente
# es asegurarse de que resource_path escriba directamente en él.
# Asumiremos que el disco persistente se montará en la raíz de tu aplicación.
# Por lo tanto, tus archivos config.json y bot_activity.log se crearán/leerán
# directamente en la ruta donde se ejecuta tu aplicación.

# Ejecuta tu bot
python3 bot.py