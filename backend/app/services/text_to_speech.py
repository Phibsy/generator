# backend/app/services/text_to_speech.py
"""
🎙️ REELS GENERATOR - Text-to-Speech Service
ElevenLabs and AWS Polly integration for high-quality voice synthesis
"""

import asyncio
from typing import Optional, List, Dict, Any, BinaryIO
import aiohttp
import boto3
import io
import logging
from pathlib import Path
import tempfile
from pydub import AudioSegment
import uuid

from ..config import settings
from ..services.file_storage import storage_service

logger = logging.getLogger(__name__)

class TextToSpeechService:
    """Service for converting text to speech with multiple providers"""
    
    def __init__(self):
        # ElevenLabs configuration
        self.elevenlabs_api_key = settings.ELEVENLABS_API_KEY
        self.elevenlabs_base_url = "https://api.elevenlabs.io/v1"
        
        # AWS Polly configuration
        self.polly_client = boto3.client(
            'polly',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # Voice mappings
        self.voice_mappings = {
            "rachel": {
                "elevenlabs_id": "21m00Tcm4TlvDq8ikWAM",
                "polly_id": "Joanna",
                "description": "Young adult female, warm and engaging"
            },
            "josh": {
                "elevenlabs_id": "TxGEqnHWrfWFTfGW9XjX",
                "polly_id": "Matthew",
                "description": "Young adult male, energetic and friendly"
            },
            "bella": {
                "elevenlabs_id": "EXAVITQu4vr4xnSDxMaL",
                "polly_id": "Amy",
                "description": "British female, professional and clear"
            },
            "adam": {
                "elevenlabs_id": "pNInz6obpgDQGcFmaJgB",
                "polly_id": "Brian",
                "description": "British male, deep and authoritative"
            }
        }
    
    # ========================================================================
    # MAIN TTS METHOD
    # ========================================================================
    
    async def generate_speech(
        self,
        text: str,
        voice_id: str = "rachel",
        speed: float = 1.0,
        use_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Generate speech from text using ElevenLabs or AWS Polly
        
        Args:
            text: The text to convert to speech
            voice_id: Voice identifier (mapped to provider-specific IDs)
            speed: Speech speed multiplier (0.5 to 2.0)
            use_fallback: Force use of AWS Polly instead of ElevenLabs
            
        Returns:
            Dict containing audio_url, duration, and metadata
        """
        
        try:
            # Validate voice_id
            if voice_id not in self.voice_mappings:
                logger.warning(f"Unknown voice_id: {voice_id}, using default")
                voice_id = "rachel"
            
            # Clean and prepare text
            cleaned_text = self._prepare_text(text)
            
            # Generate audio
            if not use_fallback and self.elevenlabs_api_key:
                audio_data = await self._generate_elevenlabs(
                    cleaned_text,
                    self.voice_mappings[voice_id]["elevenlabs_id"],
                    speed
                )
                provider = "elevenlabs"
            else:
                audio_data = await self._generate_polly(
                    cleaned_text,
                    self.voice_mappings[voice_id]["polly_id"],
                    speed
                )
                provider = "aws_polly"
            
            # Process audio (normalize, adjust speed if needed)
            processed_audio = await self._process_audio(audio_data, speed)
            
            # Upload to S3
            file_key = f"audio/{uuid.uuid4()}.mp3"
            audio_url = await storage_service.upload_audio(
                processed_audio,
                file_key
            )
            
            # Get audio duration
            duration = self._get_audio_duration(processed_audio)
            
            return {
                "audio_url": audio_url,
                "duration": duration,
                "provider": provider,
                "voice_id": voice_id,
                "text_length": len(cleaned_text),
                "file_key": file_key
            }
            
        except Exception as e:
            logger.error(f"💥 TTS generation failed: {e}")
            
            # If ElevenLabs fails, retry with Polly
            if not use_fallback:
                logger.info("Retrying with AWS Polly fallback...")
                return await self.generate_speech(text, voice_id, speed, use_fallback=True)
            
            raise
    
    # ========================================================================
    # ELEVENLABS INTEGRATION
    # ========================================================================
    
    async def _generate_elevenlabs(self, text: str, voice_id: str, speed: float) -> bytes:
        """Generate speech using ElevenLabs API"""
        
        url = f"{self.elevenlabs_base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ElevenLabs API error: {response.status} - {error_text}")
                
                return await response.read()
    
    async def get_elevenlabs_voices(self) -> List[Dict[str, Any]]:
        """Get available voices from ElevenLabs"""
        
        url = f"{self.elevenlabs_base_url}/voices"
        headers = {"xi-api-key": self.elevenlabs_api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("voices", [])
                return []
    
    async def get_elevenlabs_usage(self) -> Dict[str, Any]:
        """Get ElevenLabs API usage statistics"""
        
        url = f"{self.elevenlabs_base_url}/user"
        headers = {"xi-api-key": self.elevenlabs_api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}
    
    # ========================================================================
    # AWS POLLY INTEGRATION
    # ========================================================================
    
    async def _generate_polly(self, text: str, voice_id: str, speed: float) -> bytes:
        """Generate speech using AWS Polly"""
        
        # Polly has a character limit of 3000 for standard voices
        if len(text) > 3000:
            # Split into chunks and concatenate
            chunks = self._split_text_for_polly(text)
            audio_segments = []
            
            for chunk in chunks:
                audio_data = await self._generate_polly_chunk(chunk, voice_id, speed)
                audio_segments.append(audio_data)
            
            return self._concatenate_audio(audio_segments)
        
        return await self._generate_polly_chunk(text, voice_id, speed)
    
    async def _generate_polly_chunk(self, text: str, voice_id: str, speed: float) -> bytes:
        """Generate a single chunk of speech with Polly"""
        
        # Convert speed to SSML rate
        rate_percent = int(speed * 100)
        
        # Build SSML
        ssml = f"""
        <speak>
            <prosody rate="{rate_percent}%">
                {text}
            </prosody>
        </speak>
        """
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.polly_client.synthesize_speech(
                Text=ssml,
                TextType='ssml',
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine='neural'  # Use neural engine for better quality
            )
        )
        
        # Read audio stream
        audio_stream = response['AudioStream']
        return audio_stream.read()
    
    async def get_polly_voices(self) -> List[Dict[str, Any]]:
        """Get available voices from AWS Polly"""
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.polly_client.describe_voices()
        )
        
        return response.get('Voices', [])
    
    # ========================================================================
    # AUDIO PROCESSING
    # ========================================================================
    
    async def _process_audio(self, audio_data: bytes, speed: float) -> bytes:
        """Process audio for normalization and effects"""
        
        # Load audio
        audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
        
        # Normalize audio levels
        audio = self._normalize_audio(audio)
        
        # Apply compression for consistent volume
        audio = self._compress_audio(audio)
        
        # Add subtle fade in/out
        audio = audio.fade_in(100).fade_out(100)
        
        # Export to bytes
        output = io.BytesIO()
        audio.export(output, format="mp3", bitrate="192k")
        output.seek(0)
        
        return output.read()
    
    def _normalize_audio(self, audio: AudioSegment) -> AudioSegment:
        """Normalize audio to consistent volume"""
        
        # Calculate current dBFS
        current_dbfs = audio.dBFS
        
        # Target dBFS (YouTube/Instagram recommended)
        target_dbfs = -14.0
        
        # Calculate change needed
        change_in_dbfs = target_dbfs - current_dbfs
        
        # Apply gain
        return audio.apply_gain(change_in_dbfs)
    
    def _compress_audio(self, audio: AudioSegment) -> AudioSegment:
        """Apply dynamic range compression"""
        
        # Simple compression by reducing loud parts
        threshold = -20.0  # dB
        ratio = 4.0  # 4:1 compression
        
        # This is a simplified compression
        # In production, use more sophisticated audio processing
        return audio.compress_dynamic_range(
            threshold=threshold,
            ratio=ratio
        )
    
    # ========================================================================
    # VOICE CLONING (ELEVENLABS)
    # ========================================================================
    
    async def clone_voice(
        self,
        voice_name: str,
        audio_files: List[BinaryIO],
        description: str = ""
    ) -> str:
        """Clone a voice using ElevenLabs (requires Pro account)"""
        
        url = f"{self.elevenlabs_base_url}/voices/add"
        
        # Prepare multipart data
        data = aiohttp.FormData()
        data.add_field('name', voice_name)
        data.add_field('description', description)
        
        for i, audio_file in enumerate(audio_files):
            data.add_field(
                f'files[{i}]',
                audio_file,
                filename=f'sample_{i}.mp3',
                content_type='audio/mpeg'
            )
        
        headers = {"xi-api-key": self.elevenlabs_api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("voice_id")
                else:
                    error = await response.text()
                    raise Exception(f"Voice cloning failed: {error}")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _prepare_text(self, text: str) -> str:
        """Clean and prepare text for TTS"""
        
        # Remove excessive punctuation
        text = text.replace('...', '.')
        text = text.replace('!!!', '!')
        text = text.replace('???', '?')
        
        # Remove emojis (TTS can't pronounce them)
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub(r'', text)
        
        # Add pauses for better pacing
        text = text.replace('. ', '. <break time="300ms"/> ')
        text = text.replace('! ', '! <break time="300ms"/> ')
        text = text.replace('? ', '? <break time="300ms"/> ')
        
        return text.strip()
    
    def _split_text_for_polly(self, text: str, max_chars: int = 2900) -> List[str]:
        """Split text into chunks for Polly processing"""
        
        sentences = text.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 < max_chars:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _concatenate_audio(self, audio_segments: List[bytes]) -> bytes:
        """Concatenate multiple audio segments"""
        
        combined = AudioSegment.empty()
        
        for segment_data in audio_segments:
            segment = AudioSegment.from_mp3(io.BytesIO(segment_data))
            combined += segment
        
        output = io.BytesIO()
        combined.export(output, format="mp3")
        output.seek(0)
        
        return output.read()
    
    def _get_audio_duration(self, audio_data: bytes) -> float:
        """Get duration of audio in seconds"""
        
        audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
        return len(audio) / 1000.0  # Convert ms to seconds
    
    # ========================================================================
    # VOICE SELECTION SYSTEM
    # ========================================================================
    
    async def get_recommended_voice(
        self,
        topic: str,
        target_audience: str,
        style: str
    ) -> str:
        """Get AI-recommended voice based on content"""
        
        # Simple rule-based recommendation
        # In production, this could use ML
        
        if "gaming" in style.lower():
            return "josh"  # Young male voice for gaming
        elif "business" in style.lower():
            return "adam"  # Professional male voice
        elif "education" in style.lower():
            if "young" in target_audience.lower():
                return "rachel"  # Warm female voice
            else:
                return "bella"  # Clear British accent
        else:
            return "rachel"  # Default friendly voice
    
    async def preview_voice(self, voice_id: str, sample_text: str = None) -> str:
        """Generate a preview of a voice"""
        
        if not sample_text:
            sample_text = "Hi there! This is a preview of my voice. I hope you like how I sound!"
        
        result = await self.generate_speech(sample_text, voice_id)
        return result["audio_url"]

# ============================================================================
# VOICE PRESETS
# ============================================================================

class VoicePresets:
    """Pre-configured voice settings for different content types"""
    
    GAMING = {
        "voice_id": "josh",
        "speed": 1.1,
        "energy": "high",
        "tone": "excited"
    }
    
    EDUCATIONAL = {
        "voice_id": "rachel",
        "speed": 1.0,
        "energy": "medium",
        "tone": "clear"
    }
    
    BUSINESS = {
        "voice_id": "adam",
        "speed": 0.95,
        "energy": "professional",
        "tone": "confident"
    }
    
    STORYTELLING = {
        "voice_id": "bella",
        "speed": 0.9,
        "energy": "dramatic",
        "tone": "engaging"
    }

# Initialize service
tts_service = TextToSpeechService()
