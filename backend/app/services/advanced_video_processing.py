# backend/app/services/advanced_video_processing.py
"""
🎬 REELS GENERATOR - Advanced Video Processing Service
Week 5: Word-timing, music integration, effects, and real-time progress
"""

import asyncio
import numpy as np
from pathlib import Path
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
import logging
import aiofiles
import cv2
from dataclasses import dataclass
import librosa
import soundfile as sf
from collections import deque
import websockets
import redis.asyncio as redis

from ..config import settings
from ..services.file_storage import storage_service
from ..utils.ffmpeg_utils import ffmpeg_utils

logger = logging.getLogger(__name__)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class WordTiming:
    """Precise timing for each word"""
    word: str
    start_time: float
    end_time: float
    confidence: float = 1.0

@dataclass
class AudioAnalysis:
    """Audio analysis results"""
    waveform: np.ndarray
    tempo: float
    beats: List[float]
    energy: List[float]
    spectral_centroid: np.ndarray

@dataclass
class VideoEffect:
    """Video effect configuration"""
    type: str  # zoom, shake, pan, pulse
    start_time: float
    duration: float
    intensity: float
    parameters: Dict[str, Any]

# ============================================================================
# ADVANCED VIDEO PROCESSING SERVICE
# ============================================================================

class AdvancedVideoProcessingService:
    """Enhanced video processing with advanced features"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "reels_advanced"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Redis for progress tracking
        self.redis_client = None
        
        # Music library
        self.music_library = {
            "upbeat": {
                "file": "music/upbeat_energy.mp3",
                "bpm": 128,
                "mood": "energetic",
                "genres": ["electronic", "pop"]
            },
            "chill": {
                "file": "music/chill_vibes.mp3",
                "bpm": 90,
                "mood": "relaxed",
                "genres": ["lofi", "ambient"]
            },
            "dramatic": {
                "file": "music/dramatic_epic.mp3",
                "bpm": 100,
                "mood": "intense",
                "genres": ["orchestral", "cinematic"]
            },
            "gaming": {
                "file": "music/gaming_hype.mp3",
                "bpm": 140,
                "mood": "exciting",
                "genres": ["electronic", "dubstep"]
            }
        }
        
        # Quality presets
        self.quality_presets = {
            "low": {
                "resolution": (720, 1280),
                "fps": 24,
                "bitrate": "2M",
                "crf": 28
            },
            "medium": {
                "resolution": (1080, 1920),
                "fps": 30,
                "bitrate": "4M",
                "crf": 23
            },
            "high": {
                "resolution": (1080, 1920),
                "fps": 60,
                "bitrate": "8M",
                "crf": 19
            },
            "ultra": {
                "resolution": (2160, 3840),
                "fps": 60,
                "bitrate": "15M",
                "crf": 17
            }
        }
    
    # ========================================================================
    # WORD-LEVEL TIMING SYNCHRONIZATION
    # ========================================================================
    
    async def extract_word_timings(
        self,
        audio_path: Path,
        transcript: str
    ) -> List[WordTiming]:
        """Extract precise word timings from audio using forced alignment"""
        
        try:
            # Load audio for analysis
            waveform, sr = librosa.load(str(audio_path), sr=16000)
            
            # Perform speech recognition with timestamps
            # In production, use services like AssemblyAI or Google Speech-to-Text
            word_timings = await self._force_align_transcript(
                waveform, sr, transcript
            )
            
            return word_timings
            
        except Exception as e:
            logger.error(f"Word timing extraction failed: {e}")
            # Fallback to simple estimation
            return self._estimate_word_timings(transcript, audio_path)
    
    async def _force_align_transcript(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        transcript: str
    ) -> List[WordTiming]:
        """Force align transcript to audio (simplified version)"""
        
        words = transcript.split()
        duration = len(waveform) / sample_rate
        
        # Detect speech segments using energy
        speech_segments = self._detect_speech_segments(waveform, sample_rate)
        
        # Distribute words across speech segments
        word_timings = []
        words_per_segment = len(words) / len(speech_segments)
        
        word_idx = 0
        for seg_start, seg_end in speech_segments:
            segment_words = int(words_per_segment)
            segment_duration = seg_end - seg_start
            
            for i in range(segment_words):
                if word_idx >= len(words):
                    break
                    
                word_start = seg_start + (i * segment_duration / segment_words)
                word_end = seg_start + ((i + 1) * segment_duration / segment_words)
                
                word_timings.append(WordTiming(
                    word=words[word_idx],
                    start_time=word_start,
                    end_time=word_end,
                    confidence=0.9
                ))
                
                word_idx += 1
        
        return word_timings
    
    def _detect_speech_segments(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        threshold: float = 0.02
    ) -> List[Tuple[float, float]]:
        """Detect speech segments in audio"""
        
        # Calculate frame energy
        frame_length = int(0.025 * sample_rate)  # 25ms frames
        hop_length = int(0.010 * sample_rate)    # 10ms hop
        
        energy = []
        for i in range(0, len(waveform) - frame_length, hop_length):
            frame = waveform[i:i + frame_length]
            energy.append(np.sqrt(np.mean(frame ** 2)))
        
        energy = np.array(energy)
        
        # Find speech segments
        is_speech = energy > threshold
        segments = []
        
        start = None
        for i, speaking in enumerate(is_speech):
            time = i * hop_length / sample_rate
            
            if speaking and start is None:
                start = time
            elif not speaking and start is not None:
                segments.append((start, time))
                start = None
        
        if start is not None:
            segments.append((start, len(waveform) / sample_rate))
        
        return segments
    
    # ========================================================================
    # AUDIO ANALYSIS & MUSIC INTEGRATION
    # ========================================================================
    
    async def analyze_audio(self, audio_path: Path) -> AudioAnalysis:
        """Comprehensive audio analysis for synchronization"""
        
        # Load audio
        waveform, sr = librosa.load(str(audio_path))
        
        # Tempo and beat tracking
        tempo, beats = librosa.beat.beat_track(y=waveform, sr=sr)
        beat_times = librosa.frames_to_time(beats, sr=sr)
        
        # Energy analysis (for visual effects sync)
        hop_length = 512
        energy = librosa.feature.rms(y=waveform, hop_length=hop_length)[0]
        
        # Spectral features (for color/mood sync)
        spectral_centroid = librosa.feature.spectral_centroid(
            y=waveform, sr=sr, hop_length=hop_length
        )[0]
        
        return AudioAnalysis(
            waveform=waveform,
            tempo=tempo,
            beats=beat_times.tolist(),
            energy=energy.tolist(),
            spectral_centroid=spectral_centroid
        )
    
    async def add_background_music(
        self,
        video_path: Path,
        music_preset: str,
        volume: float = 0.1,
        auto_duck: bool = True
    ) -> Path:
        """Add background music with auto-ducking"""
        
        music_info = self.music_library.get(music_preset)
        if not music_info:
            raise ValueError(f"Unknown music preset: {music_preset}")
        
        output_path = self.temp_dir / f"music_{uuid.uuid4()}.mp4"
        
        if auto_duck:
            # Extract speech audio
            speech_audio = await ffmpeg_utils.extract_audio(
                video_path,
                self.temp_dir / "speech.wav"
            )
            
            # Analyze speech for ducking
            ducking_envelope = await self._create_ducking_envelope(speech_audio)
            
            # Apply ducking to music
            filter_complex = self._build_ducking_filter(ducking_envelope, volume)
        else:
            filter_complex = f"[1:a]volume={volume}[music];[0:a][music]amix=inputs=2:duration=shortest[a]"
        
        # Mix audio tracks
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", music_info["file"],
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-shortest",
            str(output_path)
        ]
        
        await ffmpeg_utils._run_command(cmd)
        return output_path
    
    async def _create_ducking_envelope(self, speech_path: Path) -> List[float]:
        """Create volume envelope for auto-ducking"""
        
        # Load speech audio
        speech, sr = librosa.load(str(speech_path))
        
        # Calculate speech presence
        hop_length = int(sr * 0.1)  # 100ms windows
        rms = librosa.feature.rms(y=speech, hop_length=hop_length)[0]
        
        # Smooth envelope
        envelope = []
        for i in range(len(rms)):
            if rms[i] > 0.02:  # Speech detected
                envelope.append(0.2)  # Duck to 20%
            else:
                envelope.append(1.0)  # Full volume
        
        # Smooth transitions
        smoothed = []
        window = 5
        for i in range(len(envelope)):
            start = max(0, i - window)
            end = min(len(envelope), i + window)
            smoothed.append(np.mean(envelope[start:end]))
        
        return smoothed
    
    # ========================================================================
    # VISUAL EFFECTS SYSTEM
    # ========================================================================
    
    async def apply_dynamic_effects(
        self,
        video_path: Path,
        audio_analysis: AudioAnalysis,
        effects_preset: str = "dynamic"
    ) -> Path:
        """Apply beat-synchronized visual effects"""
        
        output_path = self.temp_dir / f"effects_{uuid.uuid4()}.mp4"
        
        # Generate effects timeline
        effects = self._generate_effects_timeline(
            audio_analysis,
            effects_preset
        )
        
        # Build complex filter
        filter_complex = self._build_effects_filter(effects)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-filter_complex", filter_complex,
            "-c:a", "copy",
            str(output_path)
        ]
        
        await ffmpeg_utils._run_command(cmd)
        return output_path
    
    def _generate_effects_timeline(
        self,
        audio_analysis: AudioAnalysis,
        preset: str
    ) -> List[VideoEffect]:
        """Generate effects synchronized to audio"""
        
        effects = []
        
        if preset == "dynamic":
            # Add zoom pulses on beats
            for i, beat_time in enumerate(audio_analysis.beats[::4]):  # Every 4th beat
                effects.append(VideoEffect(
                    type="pulse",
                    start_time=beat_time,
                    duration=0.2,
                    intensity=1.1,
                    parameters={"ease": "out"}
                ))
            
            # Add shake on high energy
            energy_peaks = self._find_peaks(audio_analysis.energy)
            for peak_time in energy_peaks[:5]:  # Limit to 5 shakes
                effects.append(VideoEffect(
                    type="shake",
                    start_time=peak_time,
                    duration=0.1,
                    intensity=5,
                    parameters={"frequency": 30}
                ))
        
        elif preset == "smooth":
            # Gentle zoom and pan
            effects.append(VideoEffect(
                type="zoom",
                start_time=0,
                duration=audio_analysis.tempo * 4,  # 4 bars
                intensity=1.2,
                parameters={"ease": "inout"}
            ))
        
        return effects
    
    def _build_effects_filter(self, effects: List[VideoEffect]) -> str:
        """Build FFmpeg filter for effects"""
        
        filters = []
        
        for effect in effects:
            if effect.type == "pulse":
                # Zoom pulse effect
                scale = effect.intensity
                filters.append(
                    f"zoompan=z='if(between(t,{effect.start_time},{effect.start_time + effect.duration}),"
                    f"min(zoom+0.001,{scale}),1)':d=1:s=1080x1920"
                )
            
            elif effect.type == "shake":
                # Camera shake effect
                amplitude = effect.intensity
                filters.append(
                    f"crop=w='iw-{amplitude*2}':h='ih-{amplitude*2}':"
                    f"x='if(between(t,{effect.start_time},{effect.start_time + effect.duration}),"
                    f"{amplitude}*sin(t*{effect.parameters['frequency']}*2*PI),0)':"
                    f"y='if(between(t,{effect.start_time},{effect.start_time + effect.duration}),"
                    f"{amplitude}*cos(t*{effect.parameters['frequency']}*2*PI),0)'"
                )
        
        return ",".join(filters) if filters else "null"
    
    # ========================================================================
    # REAL-TIME PROGRESS TRACKING
    # ========================================================================
    
    async def init_progress_tracking(self):
        """Initialize Redis connection for progress tracking"""
        self.redis_client = await redis.from_url(settings.REDIS_URL)
    
    async def update_progress(
        self,
        task_id: str,
        progress: float,
        status: str,
        details: Dict[str, Any] = None
    ):
        """Update task progress in Redis"""
        
        if not self.redis_client:
            await self.init_progress_tracking()
        
        progress_data = {
            "progress": progress,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.redis_client.setex(
            f"progress:{task_id}",
            300,  # 5 minutes TTL
            json.dumps(progress_data)
        )
        
        # Publish to channel for WebSocket
        await self.redis_client.publish(
            f"progress_channel:{task_id}",
            json.dumps(progress_data)
        )
    
    # ========================================================================
    # ENHANCED SUBTITLE RENDERING
    # ========================================================================
    
    async def create_advanced_subtitles(
        self,
        word_timings: List[WordTiming],
        style_preset: str = "modern",
        animation: str = "wave"
    ) -> Path:
        """Create advanced animated subtitles with word-level timing"""
        
        subtitle_path = self.temp_dir / f"advanced_subs_{uuid.uuid4()}.ass"
        
        # ASS header with advanced styling
        ass_content = self._create_ass_header(style_preset)
        
        if animation == "wave":
            ass_content += self._create_wave_animation(word_timings)
        elif animation == "typewriter":
            ass_content += self._create_typewriter_animation(word_timings)
        elif animation == "bounce":
            ass_content += self._create_bounce_animation(word_timings)
        else:
            ass_content += self._create_fade_animation(word_timings)
        
        async with aiofiles.open(subtitle_path, 'w', encoding='utf-8') as f:
            await f.write(ass_content)
        
        return subtitle_path
    
    def _create_wave_animation(self, word_timings: List[WordTiming]) -> str:
        """Create wave-style subtitle animation"""
        
        events = []
        
        # Group words into lines (max 5 words per line)
        lines = []
        current_line = []
        
        for timing in word_timings:
            current_line.append(timing)
            if len(current_line) >= 5:
                lines.append(current_line)
                current_line = []
        
        if current_line:
            lines.append(current_line)
        
        # Create wave effect for each line
        for line_idx, line in enumerate(lines):
            line_start = line[0].start_time
            line_end = line[-1].end_time
            
            # Build line with individual word animations
            line_text = ""
            for word_idx, word_timing in enumerate(line):
                delay = word_timing.start_time - line_start
                
                # Wave effect with staggered animation
                wave_effect = (
                    f"{{\\move(640,{1100 + word_idx * 10},640,1000,{int(delay * 1000)},{int(delay * 1000 + 200)})"
                    f"\\fad(100,100)"
                    f"\\t({int(delay * 1000)},{int(delay * 1000 + 200)},\\fscx120\\fscy120)"
                    f"\\t({int(delay * 1000 + 200)},{int(delay * 1000 + 400)},\\fscx100\\fscy100)}}"
                )
                
                line_text += f"{wave_effect}{word_timing.word} "
            
            events.append(
                f"Dialogue: 0,{self._format_ass_time(line_start)},"
                f"{self._format_ass_time(line_end)},Default,,0,0,0,,{line_text.strip()}\n"
            )
        
        return "".join(events)
    
    # ========================================================================
    # QUALITY OPTIMIZATION
    # ========================================================================
    
    async def optimize_quality(
        self,
        video_path: Path,
        quality_preset: str = "medium",
        platform: Optional[str] = None
    ) -> Path:
        """Optimize video quality for target platform"""
        
        preset = self.quality_presets.get(quality_preset, self.quality_presets["medium"])
        output_path = self.temp_dir / f"optimized_{uuid.uuid4()}.mp4"
        
        # Platform-specific optimizations
        if platform == "instagram":
            preset["max_size"] = 100 * 1024 * 1024  # 100MB limit
            preset["max_duration"] = 60
        elif platform == "tiktok":
            preset["max_size"] = 287 * 1024 * 1024  # 287MB limit
            preset["max_duration"] = 180
        
        # Build optimization command
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"scale={preset['resolution'][0]}:{preset['resolution'][1]}",
            "-r", str(preset["fps"]),
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", str(preset["crf"]),
            "-b:v", preset["bitrate"],
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",  # For streaming
            str(output_path)
        ]
        
        await ffmpeg_utils._run_command(cmd)
        
        # Verify size constraints
        if platform and "max_size" in preset:
            file_size = output_path.stat().st_size
            if file_size > preset["max_size"]:
                # Re-encode with lower bitrate
                return await self._reduce_file_size(output_path, preset["max_size"])
        
        return output_path
    
    # ========================================================================
    # BATCH PROCESSING WITH PARALLEL EXECUTION
    # ========================================================================
    
    async def process_batch_parallel(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """Process multiple videos in parallel"""
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(task):
            async with semaphore:
                return await self.process_single_video(task)
        
        results = await asyncio.gather(
            *[process_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        return results
    
    # ========================================================================
    # COMPLETE PROCESSING PIPELINE
    # ========================================================================
    
    async def process_advanced_video(
        self,
        project_id: int,
        audio_url: str,
        script: str,
        settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Complete advanced video processing pipeline"""
        
        task_id = f"video_{project_id}_{uuid.uuid4()}"
        
        try:
            # Initialize progress tracking
            await self.update_progress(task_id, 0, "Starting advanced processing")
            
            # Download audio
            audio_path = await self._download_file(audio_url)
            await self.update_progress(task_id, 10, "Audio downloaded")
            
            # Extract word timings
            word_timings = await self.extract_word_timings(audio_path, script)
            await self.update_progress(task_id, 20, "Word timings extracted")
            
            # Analyze audio
            audio_analysis = await self.analyze_audio(audio_path)
            await self.update_progress(task_id, 30, "Audio analyzed")
            
            # Create advanced subtitles
            subtitle_path = await self.create_advanced_subtitles(
                word_timings,
                settings.get("subtitle_style", "modern"),
                settings.get("subtitle_animation", "wave")
            )
            await self.update_progress(task_id, 40, "Subtitles created")
            
            # Generate base video
            video_path = await self._create_base_video(
                audio_path,
                subtitle_path,
                settings.get("background", "abstract")
            )
            await self.update_progress(task_id, 50, "Base video created")
            
            # Add background music
            if settings.get("music_preset"):
                video_path = await self.add_background_music(
                    video_path,
                    settings["music_preset"],
                    settings.get("music_volume", 0.1),
                    auto_duck=True
                )
                await self.update_progress(task_id, 60, "Music added")
            
            # Apply visual effects
            if settings.get("effects_enabled", True):
                video_path = await self.apply_dynamic_effects(
                    video_path,
                    audio_analysis,
                    settings.get("effects_preset", "dynamic")
                )
                await self.update_progress(task_id, 70, "Effects applied")
            
            # Optimize quality
            final_video = await self.optimize_quality(
                video_path,
                settings.get("quality", "medium"),
                settings.get("platform")
            )
            await self.update_progress(task_id, 90, "Quality optimized")
            
            # Upload to S3
            video_url = await self._upload_video(final_video)
            await self.update_progress(task_id, 100, "Complete", {
                "video_url": video_url
            })
            
            return {
                "success": True,
                "video_url": video_url,
                "task_id": task_id,
                "processing_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Advanced processing failed: {e}")
            await self.update_progress(task_id, -1, "Failed", {
                "error": str(e)
            })
            raise
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _format_ass_time(self, seconds: float) -> str:
        """Format time for ASS subtitles"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def _find_peaks(self, data: List[float], threshold: float = 0.8) -> List[float]:
        """Find peaks in data (e.g., energy peaks)"""
        peaks = []
        max_val = max(data)
        
        for i in range(1, len(data) - 1):
            if data[i] > threshold * max_val:
                if data[i] > data[i-1] and data[i] > data[i+1]:
                    peaks.append(i * 0.1)  # Convert to time
        
        return peaks
    
    def _estimate_word_timings(self, transcript: str, audio_path: Path) -> List[WordTiming]:
        """Fallback word timing estimation"""
        words = transcript.split()
        duration = 60  # Default duration
        
        try:
            duration = asyncio.run(ffmpeg_utils.get_video_info(audio_path))["duration"]
        except:
            pass
        
        time_per_word = duration / len(words)
        
        timings = []
        for i, word in enumerate(words):
            start = i * time_per_word
            end = (i + 1) * time_per_word
            timings.append(WordTiming(word, start, end, 0.5))
        
        return timings

# Initialize service
advanced_video_service = AdvancedVideoProcessingService()
