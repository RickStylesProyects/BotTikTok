# Guía de Despliegue en Oracle Cloud - RS TikTok Downloader

Esta guía contiene todos los comandos necesarios para desplegar el bot en una instancia **Ubuntu Minimal** en Oracle Cloud, en orden de ejecución.

---

## 1. Conexión al Servidor

### Opción A: Usando SSH desde tu PC
```bash
# Dar permisos a la llave (solo Windows PowerShell)
icacls "tu_llave.key" /inheritance:r /grant:r "$env:USERNAME:R"

# Conectar
ssh -i "tu_llave.key" ubuntu@IP_DEL_SERVIDOR
```

### Opción B: Usando Oracle Cloud Shell (Recomendado si falla SSH)
Si el SSH local falla por firewall, usa la consola web de Oracle:
1. Abre **Cloud Shell** en la web de Oracle.
2. Crea el archivo de la llave privada:
   ```bash
   cat > ~/.ssh/oracle_key << 'EOF'
   -----BEGIN RSA PRIVATE KEY-----
   (Pega aquí todo el contenido de tu llave privada)
   -----END RSA PRIVATE KEY-----
   EOF
   ```
3. Asigna permisos y conecta:
   ```bash
   chmod 600 ~/.ssh/oracle_key
   ssh -i ~/.ssh/oracle_key ubuntu@IP_DEL_SERVIDOR
   ```

---

## 2. Preparación del Sistema

Una vez dentro del servidor, ejecuta estos comandos uno por uno.

### A. Crear Memoria SWAP (Vital para instancias de 1GB RAM)
```bash
# Crear archivo de 1GB
sudo fallocate -l 1G /swapfile

# Asignar permisos seguros
sudo chmod 600 /swapfile

# Formatear como swap
sudo mkswap /swapfile

# Activar swap
sudo swapon /swapfile

# Hacerlo permanente (para que dure tras reiniciar)
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### B. Instalar Docker y Herramientas
```bash
# Actualizar lista de paquetes y sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker y Git
sudo apt install -y docker.io git

# Habilitar Docker para que inicie con el sistema
sudo systemctl enable docker
sudo systemctl start docker

# Dar permisos a tu usuario para usar Docker (evita usar sudo siempre)
sudo usermod -aG docker ubuntu
```
*(Nota: Después de esto podrías necesitar salir y volver a entrar para que aplique el permiso de grupo, pero si usas `sudo` antes de docker no hay problema).*

---

## 3. Instalación del Bot

### A. Descargar el Código
```bash
# Clonar el repositorio
git clone https://github.com/RickStylesProyects/BotTikTok.git

# Entrar a la carpeta
cd BotTikTok
```

### B. Construir la Imagen (Docker Build)
Este paso descarga las dependencias y prepara el entorno aislado.
```bash
sudo docker build -t rstiktok-bot .
```

### C. Ejecutar el Bot (Docker Run)
Este comando inicia el bot en segundo plano y lo configura para revivir si se reinicia el servidor.
```bash
sudo docker run -d \
  --name tiktok-bot \
  --restart unless-stopped \
  rstiktok-bot
```

---

## 4. Comandos de Mantenimiento

### Ver si el bot está corriendo
```bash
sudo docker ps
```

### Ver los logs (para detectar errores)
```bash
sudo docker logs tiktok-bot
```
*Si quieres ver logs en tiempo real, usa `sudo docker logs -f tiktok-bot`*

### Reiniciar el bot (si hiciste cambios)
1. Descarga los cambios:
   ```bash
   git pull
   ```
2. Reconstruye la imagen:
   ```bash
   sudo docker build -t rstiktok-bot .
   ```
3. Reinicia el contenedor (borrando el anterior):
   ```bash
   sudo docker stop tiktok-bot
   sudo docker rm tiktok-bot
   sudo docker run -d --name tiktok-bot --restart unless-stopped rstiktok-bot
   ```

### Detener el bot
```bash
sudo docker stop tiktok-bot
```
