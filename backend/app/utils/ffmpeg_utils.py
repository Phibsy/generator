# backend/app/utils/ffmpeg_utils.py
"""
🎥 REELS GENERATOR - FFmpeg Utilities
Helper functions for video processing with FFmpeg
"""

import asyncio
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)

class FFmpegUtils:
    """Utility class for FFmpeg operations"""
    
    @staticmethod
    async def get_video_info(video_path: Path) -> Dict[str, Any]:
        """Get detailed video information using ffprobe"""
        
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"ffprobe failed: {stderr.decode()}")
        
        data = json.loads(stdout.decode())
        
        # Extract relevant information
        video_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
        audio_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), None)
        
        info = {
            "duration": float(data["format"].get("duration", 0)),
            "size": int(data["format"].get("size", 0)),
            "bit_rate": int(data["format"].get("bit_rate", 0)),
            "format_name": data["format"].get("format_name", ""),
        }
        
        if video_stream:
            info.update({
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                "video_codec": video_stream.get("codec_name", ""),
                "video_bitrate": int(video_stream.get("bit_rate", 0))
            })
        
        if audio_stream:
            info.update({
                "audio_codec": audio_stream.get("codec_name", ""),
                "audio_bitrate": int(audio_stream.get("bit_rate", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "channels": audio_stream.get("channels", 0)
            })
        
        return info
    
    @staticmethod
    async def extract_audio(video_path: Path, output_path: Path) -> Path:
        """Extract audio from video file"""
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-ar", "44100",
            "-ab", "192k",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def merge_audio_video(
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        audio_volume: float = 1.0
    ) -> Path:
        """Merge audio with video"""
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-filter:a", f"volume={audio_volume}",
            "-shortest",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def create_thumbnail(
        video_path: Path,
        output_path: Path,
        timestamp: float = 2.0,
        width: int = 1080,
        height: int = 1920
    ) -> Path:
        """Create thumbnail from video at specific timestamp"""
        
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-q:v", "2",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def add_subtitles(
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        style: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Add subtitles to video"""
        
        if subtitle_path.suffix == ".ass":
            subtitle_filter = f"ass={subtitle_path}"
        else:
            # For SRT subtitles with custom styling
            style_str = FFmpegUtils._build_subtitle_style(style)
            subtitle_filter = f"subtitles={subtitle_path}:force_style='{style_str}'"
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", subtitle_filter,
            "-c:a", "copy",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def concatenate_videos(
        video_paths: List[Path],
        output_path: Path,
        transition: Optional[str] = None
    ) -> Path:
        """Concatenate multiple videos with optional transitions"""
        
        # Create concat file
        concat_file = output_path.parent / "concat.txt"
        with open(concat_file, 'w') as f:
            for video_path in video_paths:
                f.write(f"file '{video_path}'\n")
        
        if transition:
            # Complex filter for transitions
            filter_complex = FFmpegUtils._build_transition_filter(len(video_paths), transition)
            
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-filter_complex", filter_complex,
                "-c:a", "copy",
                str(output_path)
            ]
        else:
            # Simple concatenation
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path)
            ]
        
        await FFmpegUtils._run_command(cmd)
        concat_file.unlink()  # Clean up
        
        return output_path
    
    @staticmethod
    async def resize_video(
        video_path: Path,
        output_path: Path,
        width: int,
        height: int,
        maintain_aspect: bool = True
    ) -> Path:
        """Resize video to specific dimensions"""
        
        if maintain_aspect:
            scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        else:
            scale_filter = f"scale={width}:{height}"
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", scale_filter,
            "-c:a", "copy",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def add_watermark(
        video_path: Path,
        watermark_path: Path,
        output_path: Path,
        position: str = "bottom_right",
        opacity: float = 0.5,
        scale: float = 0.2
    ) -> Path:
        """Add image watermark to video"""
        
        # Position mapping
        positions = {
            "top_left": "10:10",
            "top_right": "main_w-overlay_w-10:10",
            "bottom_left": "10:main_h-overlay_h-10",
            "bottom_right": "main_w-overlay_w-10:main_h-overlay_h-10",
            "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
        }
        
        pos = positions.get(position, positions["bottom_right"])
        
        filter_complex = f"[1:v]scale=iw*{scale}:ih*{scale},format=rgba,colorchannelmixer=aa={opacity}[wm];[0:v][wm]overlay={pos}"
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-i", str(watermark_path),
            "-filter_complex", filter_complex,
            "-c:a", "copy",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def trim_video(
        video_path: Path,
        output_path: Path,
        start_time: float,
        duration: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Path:
        """Trim video to specific duration"""
        
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(video_path)
        ]
        
        if duration:
            cmd.extend(["-t", str(duration)])
        elif end_time:
            cmd.extend(["-to", str(end_time)])
        
        cmd.extend([
            "-c", "copy",
            str(output_path)
        ])
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def add_fade_effects(
        video_path: Path,
        output_path: Path,
        fade_in: float = 1.0,
        fade_out: float = 1.0
    ) -> Path:
        """Add fade in/out effects to video"""
        
        # Get video duration
        info = await FFmpegUtils.get_video_info(video_path)
        duration = info["duration"]
        
        fade_out_start = duration - fade_out
        
        filter_str = f"fade=t=in:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:a", "copy",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    async def generate_waveform(
        audio_path: Path,
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
        color: str = "white"
    ) -> Path:
        """Generate waveform visualization from audio"""
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:a]showwaves=s={width}x{height}:mode=cline:rate=25:colors={color}[v]",
            "-map", "[v]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]
        
        await FFmpegUtils._run_command(cmd)
        return output_path
    
    @staticmethod
    def _build_subtitle_style(style: Optional[Dict[str, Any]]) -> str:
        """Build subtitle style string for FFmpeg"""
        
        if not style:
            style = {
                "fontname": "Arial",
                "fontsize": 24,
                "fontcolor": "white",
                "outline": 2,
                "outlinecolor": "black"
            }
        
        style_parts = []
        
        if "fontname" in style:
            style_parts.append(f"FontName={style['fontname']}")
        if "fontsize" in style:
            style_parts.append(f"FontSize={style['fontsize']}")
        if "fontcolor" in style:
            style_parts.append(f"PrimaryColour={style['fontcolor']}")
        if "outline" in style:
            style_parts.append(f"Outline={style['outline']}")
        if "outlinecolor" in style:
            style_parts.append(f"OutlineColour={style['outlinecolor']}")
        
        return ",".join(style_parts)
    
    @staticmethod
    def _build_transition_filter(num_videos: int, transition: str) -> str:
        """Build complex filter for video transitions"""
        
        if transition == "fade":
            # Fade transition between videos
            filter_parts = []
            for i in range(num_videos - 1):
                filter_parts.append(f"[{i}:v][{i+1}:v]xfade=transition=fade:duration=0.5:offset={i*10}[v{i}];")
            
            return "".join(filter_parts) + f"[v{num_videos-2}]"
        
        elif transition == "slide":
            # Slide transition
            filter_parts = []
            for i in range(num_videos - 1):
                filter_parts.append(f"[{i}:v][{i+1}:v]xfade=transition=slideleft:duration=0.5:offset={i*10}[v{i}];")
            
            return "".join(filter_parts) + f"[v{num_videos-2}]"
        
        else:
            # No transition
            return ""
    
    @staticmethod
    async def _run_command(cmd: List[str]) -> Tuple[str, str]:
        """Run FFmpeg command and return output"""
        
        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"FFmpeg command failed: {error_msg}")
        
        return stdout.decode(), stderr.decode()
    
    @staticmethod
    async def validate_ffmpeg_installation() -> bool:
        """Check if FFmpeg is properly installed"""
        
        try:
            # Check FFmpeg
            ffmpeg_cmd = ["ffmpeg", "-version"]
            ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await ffmpeg_process.communicate()
            
            # Check FFprobe
            ffprobe_cmd = ["ffprobe", "-version"]
            ffprobe_process = await asyncio.create_subprocess_exec(
                *ffprobe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await ffprobe_process.communicate()
            
            return ffmpeg_process.returncode == 0 and ffprobe_process.returncode == 0
            
        except Exception:
            return False

# Singleton instance
ffmpeg_utils = FFmpegUtils()
