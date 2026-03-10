# TikTok Downloader Module
# Uses tikwm.com API to download TikTok videos, slideshows, and audio

import os
import re
import json
import subprocess
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Callable
from config import DOWNLOAD_DIR, DEBUG_MODE

# Opcional: importar bmf si est\u00e1 disponible para decodificaci\u00f3n ByteVC2
try:
    import bmf
    HAS_BMF = True
except ImportError:
    HAS_BMF = False
    print("BMF no est\u00e1 instalado. Decodificaci\u00f3n bvc2 nativa deshabilitada.")


@dataclass
class DownloadResult:
    """Result of a TikTok download operation"""
    success: bool
    content_type: str  # 'video', 'slideshow', 'audio'
    files: List[str]  # List of downloaded file paths
    title: str = ""
    author: str = ""
    error: Optional[str] = None


def clean_downloads():
    """Clean all files in the download directory"""
    if DEBUG_MODE:
        return
        
    for file in DOWNLOAD_DIR.glob("*"):
        try:
            file.unlink()
        except Exception:
            pass


def detect_video_codec(video_path: Path) -> str:
    """Detects the video codec using ffprobe"""
    try:
        probe_cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-select_streams', 'v:0', str(video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        probe_data = json.loads(result.stdout)
        
        if probe_data.get('streams') and len(probe_data['streams']) > 0:
            return probe_data['streams'][0].get('codec_name', 'unknown')
        return 'unknown'
    except Exception as e:
        if DEBUG_MODE:
            print(f"Error detectando codec: {e}")
        return 'unknown'


def transcode_with_bmf(video_path: Path, output_path: Path, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Uses BMF to decode ByteVC2 and encode to H.264"""
    if not HAS_BMF:
        raise Exception("BMF no est\u00e1 instalado.")
        
    if progress_callback:
        progress_callback("\u2699\ufe0f [2/2] Transcodificando ByteVC2 con BMF...")
        
    try:
        # BMF Graph construction
        graph = bmf.graph()
        
        # Decode input
        video = graph.decode({"input_path": str(video_path)})
        
        # Audio normalization string
        audio_filter = "loudnorm=I=-16:LRA=11:TP=-1.5"
        
        # Encode output
        bmf.encode(
            video['video'],
            video['audio'],
            {
                "output_path": str(output_path),
                "video_params": {
                    "codec": "libx264",
                    "preset": "fast",
                    "profile": "main",
                    "pix_fmt": "yuv420p",
                    "crf": "23" # Fallback if we don't set exact bitrate
                },
                "audio_params": {
                    "codec": "aac",
                    "af": audio_filter
                }
            }
        ).run()
        
        return True
    except Exception as e:
        if DEBUG_MODE:
            print(f"BMF transcode error: {e}")
        raise e


def transcode_and_normalize(video_path: Path, progress_callback: Optional[Callable[[str], None]] = None):
    """
    Conditionally transcodes video based on codec, and always normalizes audio.
    Replaces original file if successful, otherwise keeps original.
    """
    codec = detect_video_codec(video_path)
    if DEBUG_MODE:
        print(f"Detectado codec: {codec} para {video_path.name}")
        
    temp_output = video_path.with_name(f"temp_{video_path.name}")
    
    try:
        if codec in ['bvc2', 'bytevc2', 'unknown'] and HAS_BMF:
            if progress_callback:
                progress_callback(f"\u2699\ufe0f Codificaci\u00f3n {codec} detectada. Usando BMF...")
            transcode_with_bmf(video_path, temp_output, progress_callback)
            
            if temp_output.exists() and temp_output.stat().st_size > 0:
                video_path.unlink()
                temp_output.rename(video_path)
            return
            
        # Get exact original video bitrate using ffprobe for FFmpeg
        probe_cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_streams', '-select_streams', 'v:0', str(video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            probe_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            probe_data = {}
            
        bitrate = None
        if probe_data.get('streams') and len(probe_data['streams']) > 0:
            bitrate = probe_data['streams'][0].get('bit_rate')
            
        if not bitrate:
            # Fallback to format bitrate
            probe_cmd_format = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', str(video_path)
            ]
            result_format = subprocess.run(probe_cmd_format, capture_output=True, text=True)
            try:
                probe_data_format = json.loads(result_format.stdout)
                if probe_data_format.get('format'):
                    bitrate = probe_data_format['format'].get('bit_rate')
            except json.JSONDecodeError:
                pass
                
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-map', '0:v?', '-map', '0:a?'  # Ensures both video and optional audio streams are taken
        ]
        
        # Conditional video transcoding
        if codec == 'h264':
            # Skip video transcoding, just copy
            ffmpeg_cmd.extend(['-c:v', 'copy'])
        else:
            # Transcode to h264
            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-profile:v', 'main',
                '-pix_fmt', 'yuv420p'
            ])
            if bitrate:
                ffmpeg_cmd.extend([
                    '-b:v', str(bitrate),
                    '-maxrate', str(bitrate),
                    '-bufsize', str(int(bitrate) * 2)
                ])
            else:
                ffmpeg_cmd.extend(['-crf', '23'])
                
        # Always normalize audio
        ffmpeg_cmd.extend([
            '-c:a', 'aac',
            '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5'
        ])
            
        ffmpeg_cmd.append(str(temp_output))
        
        # Determine duration to calculate progress
        duration_sec = 0
        if probe_data.get('streams') and len(probe_data['streams']) > 0:
            duration_str = probe_data['streams'][0].get('duration')
            if duration_str:
                try:
                    duration_sec = float(duration_str)
                except ValueError:
                    pass
        
        if progress_callback:
            if codec == 'h264':
                progress_callback("\u2699\ufe0f [2/2] Normalizando audio (Video H.264 listo)... 0%")
            else:
                progress_callback("\u2699\ufe0f [2/2] Transcodificando a H.264... 0%")
            
        process = subprocess.Popen(
            ffmpeg_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        stderr_output = []
        for line in process.stdout:
            stderr_output.append(line)
            if DEBUG_MODE:
                print(line, end="")
            
            if duration_sec > 0 and progress_callback and "time=" in line:
                try:
                    time_str = line.split("time=")[1].split(" ")[0]
                    h, m, s = time_str.split(":")
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    percent = min(100, int((current_sec / duration_sec) * 100))
                    if percent % 5 == 0:
                        if codec == 'h264':
                            progress_callback(f"\u2699\ufe0f [2/2] Normalizando audio... {percent}%")
                        else:
                            progress_callback(f"\u2699\ufe0f [2/2] Transcodificando a H.264... {percent}%")
                except Exception:
                    pass
                    
        process.wait()
        result_ffmpeg_code = process.returncode
        
        if DEBUG_MODE:
            if result_ffmpeg_code != 0:
                print(f"FFmpeg exit code: {result_ffmpeg_code}")
                
        if result_ffmpeg_code != 0:
            raise Exception(f"FFmpeg command failed with code {result_ffmpeg_code}")
        
        # Replace original file with transcoded one
        if temp_output.exists() and temp_output.stat().st_size > 0:
            video_path.unlink()
            temp_output.rename(video_path)
    except Exception as e:
        print(f"Transcoding error: {e}")
        if temp_output.exists():
            try:
                temp_output.unlink()
            except Exception:
                pass
        raise e


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from TikTok URL"""
    # Pattern for full URLs
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    return None


def get_tiktok_info(url: str, hd: int = 1) -> Optional[dict]:
    """
    Get TikTok video info using tikwm.com API
    Returns video data including download URLs
    """
    api_url = "https://www.tikwm.com/api/"
    
    try:
        response = requests.post(
            api_url,
            data={"url": url, "hd": hd},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == 0 and data.get("data"):
            if DEBUG_MODE:
                print("=== TIKWM API RESPONSE ===")
                print(json.dumps(data["data"], indent=2, ensure_ascii=True))
            return data["data"]
        else:
            return None
            
    except Exception as e:
        print(f"Error getting TikTok info: {e}")
        return None


def download_file(url: str, filepath: Path, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Download a file from URL to filepath"""
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=120,
            stream=True
        )
        response.raise_for_status()
        # Get total file size if available
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_percent = 0
        
        if progress_callback:
            progress_callback(f"⏳ [1/2] Obteniendo medios de TikTok... 0%")
            
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        percent = int((downloaded / total_size) * 100)
                        # Report only every 10% to prevent telegram floor
                        if percent >= last_percent + 10:
                            last_percent = percent
                            progress_callback(f"⏳ [1/2] Descargando de Servidores... {percent}%")
                            
        return True
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False


def download_video(url: str, progress_callback: Optional[Callable[[str], None]] = None) -> DownloadResult:
    """
    Download TikTok video at best quality.
    Returns DownloadResult with file paths.
    """
    clean_downloads()
    
    try:
        # Get video info from API
        info = get_tiktok_info(url)
        
        if info is None:
            return DownloadResult(
                success=False,
                content_type='video',
                files=[],
                error="No se pudo obtener información del video. Verifica que el link sea válido y público."
            )
        
        title = info.get("title", "TikTok Video")[:100]  # Limit title length
        author = info.get("author", {}).get("unique_id", "unknown")
        video_id = info.get("id", "video")
        
        # Check if it's a slideshow (images)
        images = info.get("images")
        if images and len(images) > 0:
            return download_slideshow_from_info(info, title, author)
        
        # Get video URL (prefer HD)
        video_url = info.get("hdplay") or info.get("play")
        
        if not video_url:
            return DownloadResult(
                success=False,
                content_type='video',
                files=[],
                error="No se encontró URL de descarga del video"
            )
        
        # Download video
        video_path = DOWNLOAD_DIR / f"{video_id}.mp4"
        files = []
        
        if download_file(video_url, video_path, progress_callback):
            print(f"Video downloaded, starting transcoding & normalization for {video_path.name}")
            
            try:
                transcode_and_normalize(video_path, progress_callback)
            except Exception as e:
                print(f"Transcoding failed completely: {e}")
                # Fallback to hd=0 if transcoding failed
                if "No se encontr\u00f3 URL de descarga" not in str(e):
                    if progress_callback:
                        progress_callback("\u26a0\ufe0f Codificaci\u00f3n no soportada/Fallo de memoria. Reintentando con calidad est\u00e1ndar...")
                    
                    # Try again with hd=0
                    info_sd = get_tiktok_info(url, hd=0)
                    if info_sd:
                        video_url_sd = info_sd.get("play")
                        if video_url_sd:
                            # Remove the bad HD file before downloading SD
                            if video_path.exists():
                                try:
                                    video_path.unlink()
                                except Exception:
                                    pass
                                    
                            if download_file(video_url_sd, video_path, progress_callback):
                                # Try standard transcoding one more time
                                try:
                                    transcode_and_normalize(video_path, progress_callback)
                                except Exception:
                                    pass # Just keep whatever we got if it still fails
            
            files.append(str(video_path))
            
            # Also download audio by default
            music_url = info.get("music")
            if music_url:
                audio_path = DOWNLOAD_DIR / f"{video_id}_audio.mp3"
                if download_file(music_url, audio_path):
                    files.append(str(audio_path))
            
            return DownloadResult(
                success=True,
                content_type='video',
                files=files,
                title=title,
                author=author
            )
        else:
            return DownloadResult(
                success=False,
                content_type='video',
                files=[],
                error="Error al descargar el video"
            )
            
    except Exception as e:
        return DownloadResult(
            success=False,
            content_type='video',
            files=[],
            error=str(e)
        )


def download_slideshow_from_info(info: dict, title: str, author: str, progress_callback: Optional[Callable[[str], None]] = None) -> DownloadResult:
    """
    Download TikTok slideshow (images) and audio from API info.
    """
    try:
        images = info.get("images", [])
        video_id = info.get("id", "slideshow")
        files = []
        
        # Download each image
        for i, img_url in enumerate(images):
            if progress_callback:
                progress_callback(f"⏳ Cosechando Imagen {i+1} de {len(images)}...")
            img_path = DOWNLOAD_DIR / f"{video_id}_{i+1}.jpg"
            if download_file(img_url, img_path):
                files.append(str(img_path))
        
        # Download audio if available
        music_url = info.get("music")
        if music_url:
            audio_path = DOWNLOAD_DIR / f"{video_id}_audio.mp3"
            if download_file(music_url, audio_path):
                files.append(str(audio_path))
        
        if files:
            return DownloadResult(
                success=True,
                content_type='slideshow',
                files=files,
                title=title,
                author=author
            )
        else:
            return DownloadResult(
                success=False,
                content_type='slideshow',
                files=[],
                error="No se pudieron descargar las imágenes"
            )
            
    except Exception as e:
        return DownloadResult(
            success=False,
            content_type='slideshow',
            files=[],
            error=str(e)
        )


def download_slideshow(url: str, progress_callback: Optional[Callable[[str], None]] = None) -> DownloadResult:
    """
    Download TikTok slideshow (images) and audio.
    """
    clean_downloads()
    
    info = get_tiktok_info(url)
    if info is None:
        return DownloadResult(
            success=False,
            content_type='slideshow',
            files=[],
            error="No se pudo obtener información del slideshow"
        )
    
    title = info.get("title", "TikTok Slideshow")[:100]
    author = info.get("author", {}).get("unique_id", "unknown")
    return download_slideshow_from_info(info, title, author, progress_callback)


def download_audio(url: str, progress_callback: Optional[Callable[[str], None]] = None) -> DownloadResult:
    """
    Extract and download audio from TikTok video.
    Returns DownloadResult with audio file path.
    """
    clean_downloads()
    
    try:
        info = get_tiktok_info(url)
        
        if info is None:
            return DownloadResult(
                success=False,
                content_type='audio',
                files=[],
                error="No se pudo obtener información del audio"
            )
        
        title = info.get("title", "TikTok Audio")[:100]
        author = info.get("author", {}).get("unique_id", "unknown")
        video_id = info.get("id", "audio")
        
        # Get music URL
        music_url = info.get("music")
        music_info = info.get("music_info", {})
        music_title = music_info.get("title", title) if music_info else title
        
        if not music_url:
            return DownloadResult(
                success=False,
                content_type='audio',
                files=[],
                error="No se encontró audio en este video"
            )
        
        # Download audio
        audio_path = DOWNLOAD_DIR / f"{video_id}_audio.mp3"
        
        if download_file(music_url, audio_path, progress_callback):
            return DownloadResult(
                success=True,
                content_type='audio',
                files=[str(audio_path)],
                title=music_title,
                author=author
            )
        else:
            return DownloadResult(
                success=False,
                content_type='audio',
                files=[],
                error="Error al descargar el audio"
            )
            
    except Exception as e:
        return DownloadResult(
            success=False,
            content_type='audio',
            files=[],
            error=str(e)
        )


def download_all(url: str, progress_callback: Optional[Callable[[str], None]] = None) -> DownloadResult:
    """
    Download video/slideshow and audio from TikTok.
    Automatically detects content type and downloads appropriately.
    """
    return download_video(url, progress_callback)


if __name__ == "__main__":
    # Test with sample URLs
    test_urls = [
        "https://vt.tiktok.com/ZSmsnjuCG/"
    ]
    
    for test_url in test_urls:
        print(f"\n{'='*50}")
        print(f"Testing download for: {test_url}")
        print('='*50)
        
        result = download_video(test_url)
        print(f"Success: {result.success}")
        print(f"Type: {result.content_type}")
        print(f"Title: {result.title.encode('ascii', 'ignore').decode()}")
        print(f"Author: {result.author.encode('ascii', 'ignore').decode()}")
        print(f"Files: {result.files}")
        if result.error:
            print(f"Error: {result.error}")
            
        if DEBUG_MODE:
            print(f"Archivo guardado localmente en la carpeta 'downloads' para inspección.")
        else:
            clean_downloads()
