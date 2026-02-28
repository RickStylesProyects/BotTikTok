# TikTok Telegram Bot 🎵

Bot de Telegram para descargar y enviar contenido de TikTok (videos, imágenes/slideshows, audio).

## Características

- 📹 Descarga videos de TikTok en la mejor calidad disponible
- 🖼️ Soporta slideshows/imágenes con su audio
- 🎵 Extrae audio en formato MP3 (320kbps)
- 🔗 Soporta links largos y cortos de TikTok
- ☁️ Compatible con Oracle Cloud

## Instalación Local

### Requisitos
- Python 3.9+
- FFmpeg (para extracción de audio)

### Pasos

```bash
# Clonar o copiar los archivos
cd BotTikTok

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el bot
python bot.py
```

## Despliegue en Oracle Cloud

### 1. Conectar al servidor
```bash
ssh -i tu_llave.key ubuntu@tu_ip_publica
```

### 2. Instalar dependencias del sistema
```bash
sudo apt update
sudo apt install python3-pip python3-venv ffmpeg -y
```

### 3. Subir los archivos
```bash
# Desde tu máquina local
scp -i tu_llave.key -r BotTikTok ubuntu@tu_ip_publica:/home/ubuntu/
```

### 4. Configurar el bot
```bash
cd /home/ubuntu/BotTikTok
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configurar el servicio systemd
```bash
sudo cp tiktokbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tiktokbot
sudo systemctl start tiktokbot
```

### 6. Verificar estado
```bash
sudo systemctl status tiktokbot
# Ver logs
sudo journalctl -u tiktokbot -f
```

## Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida |
| `/help` | Ayuda y ejemplos |
| `/audio <link>` | Extraer solo audio |

## Uso

1. Abre Telegram y busca `@tiktokrs_bot`
2. Envía un link de TikTok
3. ¡Recibe tu video/imágenes/audio!

## Estructura del Proyecto

```
BotTikTok/
├── bot.py              # Bot principal
├── config.py           # Configuración
├── tiktok_downloader.py # Módulo de descarga
├── requirements.txt    # Dependencias
├── tiktokbot.service   # Servicio systemd
├── downloads/          # Archivos temporales
└── README.md           # Este archivo
```

## Solución de Problemas

### El bot no responde
```bash
sudo systemctl restart tiktokbot
```

### Error de descarga
- Verifica que FFmpeg esté instalado
- Actualiza yt-dlp: `pip install -U yt-dlp`

### Video muy grande
- Telegram tiene límite de 50MB para bots
- El bot mostrará un mensaje de error si el video excede el límite

## Licencia

MIT License
