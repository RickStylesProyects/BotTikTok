# TikTok Downloader Module
# Uses tikwm.com API to download TikTok videos, slideshows, and audio

import os
import re
import json
import subprocess
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from config import DOWNLOAD_DIR


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
    for file in DOWNLOAD_DIR.glob("*"):
        try:
            file.unlink()
        except Exception:
            pass


def transcode_and_normalize(video_path: Path):
    """
    Transcodes video to H.264 matching original bitrate and normalizes audio.
    Replaces original file if successful, otherwise keeps original.
    """
    try:
        # Get exact original video bitrate using ffprobe
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
                
        temp_output = video_path.with_name(f"temp_{video_path.name}")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-map', '0:v?', '-map', '0:a?',  # Ensures both video and optional audio streams are taken
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-profile:v', 'main',  # Best balance between high and baseline for telegram compatibility
            '-pix_fmt', 'yuv420p',  # Fixes "blank/green video" issues in modern players with HDR/10-bit sources
            '-c:a', 'aac',
            '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5'  # Standard audio normalization
        ]
        
        if bitrate: # Try to maintain exact original bitrate
            ffmpeg_cmd.extend([
                '-b:v', str(bitrate),
                '-maxrate', str(bitrate),
                '-bufsize', str(int(bitrate) * 2)
            ])
        else: # Fallback
            ffmpeg_cmd.extend(['-crf', '23'])
            
        ffmpeg_cmd.append(str(temp_output))
        
        # Run ffmpeg
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Replace original file with transcoded one
        if temp_output.exists() and temp_output.stat().st_size > 0:
            video_path.unlink()
            temp_output.rename(video_path)
    except Exception as e:
        print(f"Transcoding error (keeping original file): {e}")
        temp_output = video_path.with_name(f"temp_{video_path.name}")
        if temp_output.exists():
            try:
                temp_output.unlink()
            except Exception:
                pass


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from TikTok URL"""
    # Pattern for full URLs
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    return None


def get_tiktok_info(url: str) -> Optional[dict]:
    """
    Get TikTok video info using tikwm.com API
    Returns video data including download URLs
    """
    api_url = "https://www.tikwm.com/api/"
    
    try:
        response = requests.post(
            api_url,
            data={"url": url, "hd": 1},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == 0 and data.get("data"):
            return data["data"]
        else:
            return None
            
    except Exception as e:
        print(f"Error getting TikTok info: {e}")
        return None


def download_file(url: str, filepath: Path) -> bool:
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
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False


def download_video(url: str) -> DownloadResult:
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
        
        if download_file(video_url, video_path):
            print(f"Video downloaded, starting transcoding & normalization for {video_path.name}")
            transcode_and_normalize(video_path)
            
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


def download_slideshow_from_info(info: dict, title: str, author: str) -> DownloadResult:
    """
    Download TikTok slideshow (images) and audio from API info.
    """
    try:
        images = info.get("images", [])
        video_id = info.get("id", "slideshow")
        files = []
        
        # Download each image
        for i, img_url in enumerate(images):
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


def download_slideshow(url: str) -> DownloadResult:
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
    
    return download_slideshow_from_info(info, title, author)


def download_audio(url: str) -> DownloadResult:
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
        
        if download_file(music_url, audio_path):
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


def download_all(url: str) -> DownloadResult:
    """
    Download video/slideshow and audio from TikTok.
    Automatically detects content type and downloads appropriately.
    """
    return download_video(url)


if __name__ == "__main__":
    # Test with sample URLs
    test_urls = [
        "https://www.tiktok.com/@gosari542/video/7600030107658472722",
        "https://vt.tiktok.com/ZSaUnMTho/"
    ]
    
    for test_url in test_urls:
        print(f"\n{'='*50}")
        print(f"Testing download for: {test_url}")
        print('='*50)
        
        result = download_video(test_url)
        print(f"Success: {result.success}")
        print(f"Type: {result.content_type}")
        print(f"Title: {result.title}")
        print(f"Author: {result.author}")
        print(f"Files: {result.files}")
        if result.error:
            print(f"Error: {result.error}")
        
        clean_downloads()
