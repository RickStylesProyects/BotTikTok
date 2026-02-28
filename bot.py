# TikTok Telegram Bot
# Downloads and sends TikTok videos, images, and audio

import re
import os
import asyncio
import logging
from pathlib import Path
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatAction

from config import BOT_TOKEN, TIKTOK_PATTERNS, DOWNLOAD_DIR
from tiktok_downloader import download_video, download_audio, clean_downloads, DownloadResult

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def is_tiktok_url(text: str) -> bool:
    """Check if the text contains a TikTok URL"""
    for pattern in TIKTOK_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def extract_tiktok_url(text: str) -> str:
    """Extract TikTok URL from text"""
    for pattern in TIKTOK_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    welcome_message = """
🎬 *RS TikTok Downloader*

Bot para descargar videos e imágenes de TikTok.

Envía un link de TikTok para comenzar.
"""
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_message = """
📖 *RS TikTok Downloader - Guía de Uso*

*Para descargar contenido:*
Solo envía el link de TikTok:
`https://www.tiktok.com/@usuario/video/123456`
o
`https://vt.tiktok.com/XXXXX/`

*¿Qué recibirás?*
• Videos: Video + Audio MP3
• Slideshows: Imágenes + Audio MP3

*Formatos de links soportados:*
• Links largos de TikTok
• Links cortos (vt.tiktok.com, vm.tiktok.com)

*Nota:* Los videos privados no se pueden descargar.
"""
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)


async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /audio command - Extract only audio"""
    # Check if URL is provided with command
    if context.args and len(context.args) > 0:
        url = context.args[0]
        if is_tiktok_url(url):
            await process_audio_request(update, url)
        else:
            await update.message.reply_text(
                "❌ El link proporcionado no parece ser de TikTok.\n"
                "Ejemplo: `/audio https://vt.tiktok.com/XXXXX/`",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        # Store state that next message should be processed as audio request
        context.user_data['waiting_for_audio_url'] = True
        await update.message.reply_text(
            "🎵 Envíame el link de TikTok para extraer el audio:"
        )


async def process_audio_request(update: Update, url: str) -> None:
    """Process audio extraction request"""
    status_message = await update.message.reply_text(
        "🎵 *Extrayendo audio...*\nEsto puede tomar unos segundos.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show typing action
    await update.message.chat.send_action(ChatAction.UPLOAD_VOICE)
    
    try:
        # Download audio in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_audio, url)
        
        if result.success and result.files:
            audio_path = Path(result.files[0])
            
            # Send audio
            with open(audio_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=result.title,
                    caption=f"🎵 {result.title}"
                )
            
            await status_message.delete()
            
            # Clean up
            clean_downloads()
        else:
            await status_message.edit_text(
                f"❌ *Error al extraer audio:*\n{result.error}",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        await status_message.edit_text(
            f"❌ *Error:* {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        clean_downloads()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages with TikTok links"""
    text = update.message.text
    
    # Check if waiting for audio URL
    if context.user_data.get('waiting_for_audio_url'):
        context.user_data['waiting_for_audio_url'] = False
        if is_tiktok_url(text):
            await process_audio_request(update, extract_tiktok_url(text))
        else:
            await update.message.reply_text(
                "❌ El link no parece ser de TikTok. Intenta de nuevo con /audio"
            )
        return
    
    # Check if message contains TikTok URL
    if not is_tiktok_url(text):
        await update.message.reply_text(
            "👋 Envíame un link de TikTok para descargar el contenido.\n"
            "Usa /help para más información."
        )
        return
    
    url = extract_tiktok_url(text)
    logger.info(f"Processing TikTok URL: {url}")
    
    # Send processing message
    status_message = await update.message.reply_text(
        "⏳ *Descargando...*\nEsto puede tomar unos segundos.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show typing action
    await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    
    try:
        # Download video in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_video, url)
        
        if result.success:
            await send_content(update, result, status_message)
        else:
            await status_message.edit_text(
                f"❌ *Error al descargar:*\n{result.error}",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        await status_message.edit_text(
            f"❌ *Error:* {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        clean_downloads()


async def send_content(update: Update, result: DownloadResult, status_message) -> None:
    """Send downloaded content to user"""
    try:
        if result.content_type == 'video':
            # Send video
            video_path = Path(result.files[0])
            
            # Check file size (Telegram limit is 50MB for bots)
            file_size = video_path.stat().st_size
            if file_size > 50 * 1024 * 1024:  # 50 MB
                await status_message.edit_text(
                    "❌ El video es demasiado grande (>50MB).\n"
                    "Telegram tiene un límite de 50MB para bots."
                )
                return
            
            await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
            
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"📹 {result.title}",
                    supports_streaming=True
                )
            
            # Send audio if available (videos now include audio by default)
            audio_files = [f for f in result.files if Path(f).suffix.lower() in ['.mp3', '.m4a', '.opus']]
            if audio_files:
                await update.message.chat.send_action(ChatAction.UPLOAD_VOICE)
                with open(audio_files[0], 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=f"Audio - {result.title}",
                        caption="🎵 Audio del video"
                    )
            
            await status_message.delete()
            
        elif result.content_type == 'slideshow':
            # Send images as media group
            image_files = [f for f in result.files if Path(f).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]
            audio_files = [f for f in result.files if Path(f).suffix.lower() in ['.mp3', '.m4a', '.opus']]
            video_files = [f for f in result.files if Path(f).suffix.lower() in ['.mp4', '.webm']]
            
            if image_files:
                # Send images as album (max 10 per group)
                await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
                
                media_group = []
                for i, img_path in enumerate(image_files[:10]):
                    with open(img_path, 'rb') as img_file:
                        if i == 0:
                            media_group.append(InputMediaPhoto(
                                media=img_file.read(),
                                caption=f"🖼️ {result.title}"
                            ))
                        else:
                            media_group.append(InputMediaPhoto(media=img_file.read()))
                
                if media_group:
                    await update.message.reply_media_group(media=media_group)
            
            elif video_files:
                # If slideshow converted to video
                with open(video_files[0], 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"📹 {result.title}",
                        supports_streaming=True
                    )
            
            # Send audio if available
            if audio_files:
                await update.message.chat.send_action(ChatAction.UPLOAD_VOICE)
                with open(audio_files[0], 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=f"Audio - {result.title}",
                        caption="🎵 Audio del slideshow"
                    )
            
            await status_message.delete()
            
        elif result.content_type == 'audio':
            # Send audio
            audio_path = Path(result.files[0])
            
            await update.message.chat.send_action(ChatAction.UPLOAD_VOICE)
            
            with open(audio_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=result.title,
                    caption=f"🎵 {result.title}"
                )
            
            await status_message.delete()
            
    except Exception as e:
        logger.error(f"Error sending content: {e}")
        await status_message.edit_text(
            f"❌ *Error al enviar:* {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Ocurrió un error. Por favor intenta de nuevo."
        )


def main() -> None:
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Create downloads directory
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    
    # Start bot
    logger.info("Starting RS TikTok Downloader Bot...")
    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    
    # Run bot with polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
