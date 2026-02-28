# RS TikTok Downloader - Main entry point
# Runs Telegram bot + Health check server for HuggingFace Spaces

import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler for HuggingFace Spaces"""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>RS TikTok Downloader</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    display: flex; 
                    justify-content: center; 
                    align-items: center; 
                    height: 100vh; 
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container { 
                    text-align: center; 
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                }
                h1 { font-size: 2.5em; margin-bottom: 10px; }
                p { font-size: 1.2em; opacity: 0.9; }
                .status { 
                    display: inline-block;
                    padding: 8px 20px;
                    background: #00c853;
                    border-radius: 20px;
                    margin-top: 20px;
                }
                a { color: white; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 RS TikTok Downloader</h1>
                <p>Bot de Telegram para descargar videos de TikTok</p>
                <div class="status">✓ Bot Activo</div>
                <p style="margin-top: 30px;">
                    <a href="https://t.me/tiktokrs_bot" target="_blank">
                        Abrir en Telegram →
                    </a>
                </p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def run_health_server():
    """Run health check HTTP server on port 7860"""
    server = HTTPServer(('0.0.0.0', 7860), HealthHandler)
    logger.info("Health server running on port 7860")
    server.serve_forever()


def run_bot():
    """Run the Telegram bot"""
    from bot import main
    main()


if __name__ == "__main__":
    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health server started")
    
    # Run Telegram bot in main thread
    logger.info("Starting Telegram bot...")
    run_bot()
