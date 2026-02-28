#!/bin/bash

# Script para actualizar el Bot de TikTok en Oracle Cloud (Contenedor Docker)
echo "=========================================="
echo "Iniciando actualizacion de rstiktok-bot..."
echo "=========================================="

# Bajar los cambios más recientes de GitHub
echo "-> Descargando ultimo codigo desde GitHub..."
git fetch origin main
git reset --hard origin/main

# Detener y borrar el contenedor viejo
echo "-> Deteniendo contenedor antiguo..."
docker stop tiktok-bot || true
docker rm tiktok-bot || true

# Recompilar la imagen de Docker para asegurar que se instalen nuevas dependencias
echo "-> Reconstruyendo imagen (esto puede tomar varios minutos si hay cambios)..."
docker build -t rstiktok-bot .

# Correr el nuevo contenedor de forma persistente
echo "-> Desplegando el nuevo bbot..."
docker run -d --name tiktok-bot -p 7860:7860 --restart unless-stopped rstiktok-bot

# Limpieza opcional de imágenes sueltas creadas (Dangling images) para ahorrar espacio
echo "-> Limpiando caché y archivos innecesarios de Docker..."
docker image prune -f

echo "=========================================="
echo "¡Actualizacion Finalizada Exitosamente!"
echo "Puedes revisar los logs con: docker logs -f tiktok-bot"
echo "=========================================="
