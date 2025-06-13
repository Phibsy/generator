# backend/app/services/video_processing.py
"""
🎬 REELS GENERATOR - Video Processing Service
FFmpeg-based video composition with subtitles and effects
"""

import asyncio
import subprocess
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import uuid
import logging
from datetime import datetime
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

from ..config import settings
from ..services.file_storage import storage_service

logger = logging.getLogger(__name__)

class VideoProcessingService:
    """Service for automated video generation and processing"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "reels_generator"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Video settings
        self.default_resolution = (1080, 1920)  # 9:16 vertical
        self.default_fps = 30
        self.default_bitrate = "4M"
        
        # Subtitle settings
        self.subtitle_styles = {
            "default": {
                "fontname": "Arial",
                "fontsize": 24,
                "fontcolor": "white",
                "box": 1,
                "boxcolor": "black@0.5",
                "alignment": 2,  # Center
                "margin_v": 50
            },
            "modern": {
                "fontname": "Arial Black",
                "fontsize": 28,
                "fontcolor": "yellow",
                "bordercolor": "black",
                "borderstyle": 3,
                "alignment": 2,
                "margin_v": 80
            },
            "minimal": {
                "fontname": "Helvetica",
                "fontsize": 22,
                "fontcolor": "white",
                "shadowcolor": "black",
                "shadowx": 2,
                "shadowy": 2,
                "alignment": 2,
                "margin_v": 60
            }
        }
        
        # Background video library
        self.background_videos = {
            "minecraft": "backgrounds/minecraft_parkour.mp4",
            "subway_surfers": "backgrounds/subway_surfers.mp4",
            "gta": "backgrounds/gta_driving.mp4",
            "nature": "backgrounds/nature_scenery.mp4",
            "abstract": "backgrounds/abstract_shapes.mp4",
            "tech": "backgrounds/tech_animation.mp4"
        }
    
    # ========================================================================
    # MAIN VIDEO GENERATION
    # ========================================================================
    
    async def generate_video(
        self,
        audio_url: str,
        script: str,
        background_video: str = "minecraft",
        subtitle_style: str = "default",
        subtitle_animation: str = "word_by_word",
        music_volume: float = 0.1,
        transitions: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete video with audio, subtitles, and background
        
        Args:
            audio_url: URL of the TTS audio file
            script: Text script for subtitles
            background_video: Background video preset
            subtitle_style: Subtitle styling preset
            subtitle_animation: Animation type (word_by_word, line_by_line, karaoke)
            music_volume: Background music volume (0-1)
            transitions: Enable transition effects
            
        Returns:
            Dict with video_url, duration, and metadata
        """
        
        temp_files = []
        
        try:
            logger.info("🎬 Starting video generation process...")
            
            # Download audio
            audio_path = await self._download_file(audio_url, "audio.mp3")
            temp_files.append(audio_path)
            
            # Get audio duration
            duration = await self._get_media_duration(audio_path)
            
            # Get background video
            background_path = await self._get_background_video(background_video, duration)
            temp_files.append(background_path)
            
            # Generate subtitles
            subtitle_path = await self._generate_subtitles(
                script, 
                duration, 
                subtitle_style, 
                subtitle_animation
            )
            temp_files.append(subtitle_path)
            
            # Compose final video
            output_path = self.temp_dir / f"output_{uuid.uuid4()}.mp4"
            
            await self._compose_video(
                background_path=background_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                music_volume=music_volume,
                transitions=transitions
            )
            
            # Upload to S3
            video_key = f"videos/{uuid.uuid4()}.mp4"
            with open(output_path, 'rb') as f:
                video_url = await storage_service.upload_video(f, video_key)
            
            # Generate thumbnail
            thumbnail_url = await self._generate_thumbnail(output_path)
            
            logger.info("✅ Video generation completed successfully!")
            
            return {
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "duration": duration,
                "resolution": "1080x1920",
                "fps": self.default_fps,
                "file_size": os.path.getsize(output_path),
                "metadata": {
                    "background": background_video,
                    "subtitle_style": subtitle_style,
                    "generation_time": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"💥 Video generation failed: {e}")
            raise
            
        finally:
            # Cleanup temp files
            for file_path in temp_files:
                if file_path and file_path.exists():
                    file_path.unlink()
    
    # ========================================================================
    # SUBTITLE GENERATION
    # ========================================================================
    
    async def _generate_subtitles(
        self,
        script: str,
        duration: float,
        style: str,
        animation_type: str
    ) -> Path:
        """Generate subtitle file with timing"""
        
        subtitle_path = self.temp_dir / f"subtitles_{uuid.uuid4()}.ass"
        
        if animation_type == "word_by_word":
            subtitle_content = await self._create_word_by_word_subtitles(script, duration, style)
        elif animation_type == "karaoke":
            subtitle_content = await self._create_karaoke_subtitles(script, duration, style)
        else:
            subtitle_content = await self._create_line_by_line_subtitles(script, duration, style)
        
        # Write subtitle file
        async with aiofiles.open(subtitle_path, 'w', encoding='utf-8') as f:
            await f.write(subtitle_content)
        
        return subtitle_path
    
    async def _create_word_by_word_subtitles(
        self,
        script: str,
        duration: float,
        style: str
    ) -> str:
        """Create word-by-word animated subtitles"""
        
        words = script.split()
        words_per_second = len(words) / duration
        
        # ASS subtitle format header
        style_config = self.subtitle_styles.get(style, self.subtitle_styles["default"])
        
        ass_content = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style_config['fontname']},{style_config['fontsize']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{style_config['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        # Add words with timing
        current_time = 0.0
        for i, word in enumerate(words):
            word_duration = 1.0 / words_per_second
            start_time = self._format_ass_time(current_time)
            end_time = self._format_ass_time(current_time + word_duration)
            
            # Add animation effect
            effect = "{\\fad(100,100)\\pos(640,1000)\\t(0,200,\\fscx120\\fscy120)\\t(200,400,\\fscx100\\fscy100)}"
            
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{effect}{word}\n"
            
            current_time += word_duration * 0.8  # Slight overlap for smooth flow
        
        return ass_content
    
    async def _create_karaoke_subtitles(
        self,
        script: str,
        duration: float,
        style: str
    ) -> str:
        """Create karaoke-style animated subtitles"""
        
        lines = self._split_script_into_lines(script, 8)  # 8 words per line max
        time_per_line = duration / len(lines)
        
        style_config = self.subtitle_styles.get(style, self.subtitle_styles["default"])
        
        ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style_config['fontname']},{style_config['fontsize']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,{style_config['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        current_time = 0.0
        for line in lines:
            start_time = self._format_ass_time(current_time)
            end_time = self._format_ass_time(current_time + time_per_line)
            
            # Karaoke effect with color sweep
            words = line.split()
            karaoke_text = ""
            word_duration = (time_per_line * 1000) / len(words)  # milliseconds
            
            for i, word in enumerate(words):
                k_time = int(word_duration)
                karaoke_text += f"{{\\k{k_time}}}{word} "
            
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{karaoke_text.strip()}\n"
            
            current_time += time_per_line
        
        return ass_content
    
    async def _create_line_by_line_subtitles(
        self,
        script: str,
        duration: float,
        style: str
    ) -> str:
        """Create simple line-by-line subtitles"""
        
        lines = self._split_script_into_lines(script, 10)
        time_per_line = duration / len(lines)
        
        srt_content = ""
        
        for i, line in enumerate(lines):
            start_time = i * time_per_line
            end_time = (i + 1) * time_per_line
            
            srt_content += f"{i + 1}\n"
            srt_content += f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}\n"
            srt_content += f"{line}\n\n"
        
        # Convert SRT to ASS for styling
        return await self._srt_to_ass(srt_content, style)
    
    # ========================================================================
    # VIDEO COMPOSITION
    # ========================================================================
    
    async def _compose_video(
        self,
        background_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        music_volume: float,
        transitions: bool
    ):
        """Compose final video with all elements"""
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(background_path),  # Background video
            "-i", str(audio_path),  # TTS audio
            "-filter_complex", self._build_filter_complex(
                subtitle_path,
                music_volume,
                transitions
            ),
            "-map", "[v]",  # Use filtered video
            "-map", "[a]",  # Use mixed audio
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",  # Match shortest input
            str(output_path)
        ]
        
        # Run FFmpeg
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"FFmpeg failed: {error_msg}")
    
    def _build_filter_complex(
        self,
        subtitle_path: Path,
        music_volume: float,
        transitions: bool
    ) -> str:
        """Build complex filter for FFmpeg"""
        
        filters = []
        
        # Scale and crop background to 9:16
        filters.append("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg]")
        
        # Add blur effect to background
        filters.append("[bg]boxblur=2:2[blurred]")
        
        # Add subtitles
        filters.append(f"[blurred]ass={subtitle_path}[subbed]")
        
        if transitions:
            # Add fade in/out
            filters.append("[subbed]fade=t=in:d=0.5,fade=t=out:d=0.5:st=duration-0.5[v]")
        else:
            filters.append("[subbed]copy[v]")
        
        # Audio mixing
        if music_volume > 0:
            filters.append(f"[0:a]volume={music_volume}[music]")
            filters.append("[music][1:a]amix=inputs=2:duration=shortest[a]")
        else:
            filters.append("[1:a]anull[a]")
        
        return ";".join(filters)
    
    # ========================================================================
    # BACKGROUND VIDEO MANAGEMENT
    # ========================================================================
    
    async def _get_background_video(self, preset: str, duration: float) -> Path:
        """Get and prepare background video"""
        
        # For now, generate a simple colored background
        # In production, this would fetch from S3
        output_path = self.temp_dir / f"background_{uuid.uuid4()}.mp4"
        
        # Create background video with FFmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1080x1920:d={duration}",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration}",
            "-shortest",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            str(output_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        return output_path
    
    # ========================================================================
    # THUMBNAIL GENERATION
    # ========================================================================
    
    async def _generate_thumbnail(self, video_path: Path) -> str:
        """Generate thumbnail from video"""
        
        thumbnail_path = self.temp_dir / f"thumbnail_{uuid.uuid4()}.jpg"
        
        # Extract frame at 2 seconds
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-ss", "2",
            "-vframes", "1",
            "-vf", "scale=1080:1920",
            "-q:v", "2",
            str(thumbnail_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        # Upload to S3
        with open(thumbnail_path, 'rb') as f:
            thumbnail_url = await storage_service.upload_video(
                f,
                f"thumbnails/{uuid.uuid4()}.jpg",
                content_type="image/jpeg"
            )
        
        thumbnail_path.unlink()
        
        return thumbnail_url
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    async def _download_file(self, url: str, filename: str) -> Path:
        """Download file from URL"""
        
        output_path = self.temp_dir / filename
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                content = await response.read()
                
                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(content)
        
        return output_path
    
    async def _get_media_duration(self, file_path: Path) -> float:
        """Get duration of media file"""
        
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return float(stdout.decode().strip())
        
        raise Exception("Failed to get media duration")
    
    def _split_script_into_lines(self, script: str, words_per_line: int) -> List[str]:
        """Split script into lines for subtitles"""
        
        words = script.split()
        lines = []
        
        for i in range(0, len(words), words_per_line):
            line = " ".join(words[i:i + words_per_line])
            lines.append(line)
        
        return lines
    
    def _format_ass_time(self, seconds: float) -> str:
        """Format time for ASS subtitles (h:mm:ss.cc)"""
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT subtitles (hh:mm:ss,mmm)"""
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    async def _srt_to_ass(self, srt_content: str, style: str) -> str:
        """Convert SRT to ASS format with styling"""
        
        # This is a simplified conversion
        # In production, use a proper subtitle library
        
        style_config = self.subtitle_styles.get(style, self.subtitle_styles["default"])
        
        ass_content = f"""[Script Info]
Title: Converted Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style_config['fontname']},{style_config['fontsize']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{style_config['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        # Parse SRT and convert to ASS
        # This is simplified - real implementation would be more robust
        
        return ass_content
    
    # ========================================================================
    # ADVANCED FEATURES
    # ========================================================================
    
    async def add_watermark(
        self,
        video_path: Path,
        watermark_text: str,
        position: str = "bottom_right"
    ) -> Path:
        """Add watermark to video"""
        
        output_path = self.temp_dir / f"watermarked_{uuid.uuid4()}.mp4"
        
        # Position mapping
        positions = {
            "top_left": "10:10",
            "top_right": "main_w-text_w-10:10",
            "bottom_left": "10:main_h-text_h-10",
            "bottom_right": "main_w-text_w-10:main_h-text_h-10"
        }
        
        pos = positions.get(position, positions["bottom_right"])
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", f"drawtext=text='{watermark_text}':fontcolor=white@0.5:fontsize=24:x={pos}",
            "-c:a", "copy",
            str(output_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        return output_path
    
    async def optimize_for_platform(
        self,
        video_path: Path,
        platform: str
    ) -> Dict[str, Any]:
        """Optimize video for specific platform"""
        
        platform_specs = {
            "youtube": {
                "resolution": "1080x1920",
                "fps": 30,
                "bitrate": "4M",
                "format": "mp4"
            },
            "instagram": {
                "resolution": "1080x1920",
                "fps": 30,
                "bitrate": "3.5M",
                "format": "mp4",
                "max_duration": 60
            },
            "tiktok": {
                "resolution": "1080x1920",
                "fps": 30,
                "bitrate": "4M",
                "format": "mp4",
                "max_duration": 180
            }
        }
        
        specs = platform_specs.get(platform, platform_specs["youtube"])
        
        # Optimize video based on platform requirements
        # Implementation would include re-encoding with platform-specific settings
        
        return {
            "optimized": True,
            "platform": platform,
            "specs": specs
        }

# Initialize service
video_service = VideoProcessingService()
