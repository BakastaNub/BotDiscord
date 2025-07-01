# Usa una imagen oficial de Python como base
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos necesarios
COPY . .

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Ejecuta el bot cuando el contenedor se inicie
CMD ["python", "bot.py"]