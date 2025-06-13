# backend/app/services/asset_analysis.py
"""
🤖 REELS GENERATOR - Asset Analysis Service
AI-powered analysis and auto-tagging of assets
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
import logging
import numpy as np
from pathlib import Path
import cv2
import librosa
from PIL import Image
import imagehash
import json

from ..utils.ffmpeg_utils import ffmpeg_utils
from ..services.content_generation import content_service
from ..database import AsyncSessionLocal
from ..models.assets import Asset, AssetType, ContentRating
from sqlalchemy import update

logger = logging.getLogger(__name__)

class AssetAnalysisService:
    """Service for AI-powered asset analysis"""
    
    def __init__(self):
        self.scene_categories = {
            "gaming": ["gameplay", "minecraft", "fortnite", "gta", "racing", "fps"],
            "nature": ["landscape", "ocean", "forest", "mountains", "sky", "animals"],
            "urban": ["city", "traffic", "buildings", "street", "nightlife"],
            "tech": ["computers", "data", "futuristic", "abstract", "digital"],
            "lifestyle": ["food", "fitness", "fashion", "travel", "home"],
            "sports": ["football", "basketball", "soccer", "extreme", "gym"]
        }
        
        self.music_moods = {
            "energetic": {"energy": (0.7, 1.0), "tempo": (120, 180)},
            "calm": {"energy": (0.0, 0.4), "tempo": (60, 100)},
            "dramatic": {"energy": (0.5, 0.8), "tempo": (80, 120)},
            "upbeat": {"energy": (0.6, 0.9), "tempo": (110, 140)},
            "melancholic": {"energy": (0.2, 0.5), "tempo": (70, 110)}
        }
    
    # ========================================================================
    # MAIN ANALYSIS METHOD
    # ========================================================================
    
    async def analyze_asset(self, asset: Asset) -> Dict[str, Any]:
        """Perform comprehensive analysis on an asset"""
        
        try:
            logger.info(f"🔍 Analyzing asset {asset.asset_id} ({asset.asset_type})")
            
            analysis_result = {}
            
            if asset.asset_type == AssetType.BACKGROUND_VIDEO:
                analysis_result = await self._analyze_video(asset)
            elif asset.asset_type in [AssetType.MUSIC, AssetType.SOUND_EFFECT]:
                analysis_result = await self._analyze_audio(asset)
            elif asset.asset_type == AssetType.IMAGE:
                analysis_result = await self._analyze_image(asset)
            
            # Update asset with analysis results
            await self._update_asset_with_analysis(asset.id, analysis_result)
            
            logger.info(f"✅ Analysis complete for asset {asset.asset_id}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"💥 Asset analysis failed: {e}")
            raise
    
    # ========================================================================
    # VIDEO ANALYSIS
    # ========================================================================
    
    async def _analyze_video(self, asset: Asset) -> Dict[str, Any]:
        """Analyze video asset for content and characteristics"""
        
        # Download video temporarily
        video_path = await self._download_asset(asset.cdn_url)
        
        try:
            # Get video info
            video_info = await ffmpeg_utils.get_video_info(video_path)
            
            # Extract frames for analysis
            frames = await self._extract_video_frames(video_path, num_frames=10)
            
            # Analyze scenes
            scene_analysis = await self._analyze_video_scenes(frames)
            
            # Detect dominant colors
            dominant_colors = self._extract_dominant_colors(frames)
            
            # Analyze motion and energy
            motion_analysis = self._analyze_video_motion(frames)
            
            # Generate tags
            tags = self._generate_video_tags(
                scene_analysis,
                motion_analysis,
                video_info
            )
            
            # Determine content rating
            content_rating = await self._determine_content_rating(frames)
            
            analysis_result = {
                "duration": video_info["duration"],
                "resolution": f"{video_info['width']}x{video_info['height']}",
                "fps": video_info["fps"],
                "tags": tags,
                "categories": scene_analysis["categories"],
                "dominant_colors": dominant_colors,
                "energy_level": motion_analysis["energy_level"],
                "content_rating": content_rating,
                "scene_types": scene_analysis["scene_types"],
                "metadata": {
                    "codec": video_info.get("video_codec", "unknown"),
                    "bitrate": video_info.get("video_bitrate", 0),
                    "motion_intensity": motion_analysis["motion_intensity"],
                    "scene_changes": scene_analysis["scene_changes"]
                }
            }
            
            return analysis_result
            
        finally:
            # Cleanup
            video_path.unlink()
    
    async def _extract_video_frames(
        self,
        video_path: Path,
        num_frames: int = 10
    ) -> List[np.ndarray]:
        """Extract frames from video for analysis"""
        
        cap = cv2.VideoCapture(str(video_path))
        frames = []
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
            
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)
            
            return frames
            
        finally:
            cap.release()
    
    async def _analyze_video_scenes(
        self,
        frames: List[np.ndarray]
    ) -> Dict[str, Any]:
        """Analyze video scenes using computer vision"""
        
        scene_types = []
        categories = set()
        scene_changes = 0
        
        # Simple scene detection using image hashing
        prev_hash = None
        
        for frame in frames:
            # Convert to PIL Image
            pil_image = Image.fromarray(frame)
            
            # Calculate perceptual hash
            current_hash = imagehash.average_hash(pil_image)
            
            # Detect scene change
            if prev_hash and current_hash - prev_hash > 10:
                scene_changes += 1
            
            prev_hash = current_hash
            
            # Classify scene (simplified - in production use ML model)
            scene_type = self._classify_scene(frame)
            scene_types.append(scene_type)
            
            # Map to categories
            for category, keywords in self.scene_categories.items():
                if any(keyword in scene_type.lower() for keyword in keywords):
                    categories.add(category)
        
        return {
            "scene_types": list(set(scene_types)),
            "categories": list(categories),
            "scene_changes": scene_changes
        }
    
    def _classify_scene(self, frame: np.ndarray) -> str:
        """Classify scene type (simplified version)"""
        
        # In production, use a trained CNN model
        # This is a simplified heuristic approach
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Calculate image statistics
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        # Simple classification based on brightness patterns
        if mean_brightness < 50:
            return "dark_scene"
        elif mean_brightness > 200:
            return "bright_scene"
        elif std_brightness > 60:
            return "high_contrast"
        else:
            return "normal_scene"
    
    def _analyze_video_motion(
        self,
        frames: List[np.ndarray]
    ) -> Dict[str, Any]:
        """Analyze motion and energy in video"""
        
        motion_scores = []
        
        for i in range(1, len(frames)):
            # Calculate optical flow between consecutive frames
            prev_gray = cv2.cvtColor(frames[i-1], cv2.COLOR_RGB2GRAY)
            curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_RGB2GRAY)
            
            # Calculate frame difference
            diff = cv2.absdiff(prev_gray, curr_gray)
            motion_score = np.mean(diff) / 255.0
            
            motion_scores.append(motion_score)
        
        avg_motion = np.mean(motion_scores)
        
        # Determine energy level
        if avg_motion > 0.3:
            energy_level = 0.9
            motion_intensity = "high"
        elif avg_motion > 0.1:
            energy_level = 0.6
            motion_intensity = "medium"
        else:
            energy_level = 0.3
            motion_intensity = "low"
        
        return {
            "energy_level": energy_level,
            "motion_intensity": motion_intensity,
            "motion_scores": motion_scores
        }
    
    # ========================================================================
    # AUDIO ANALYSIS
    # ========================================================================
    
    async def _analyze_audio(self, asset: Asset) -> Dict[str, Any]:
        """Analyze audio asset for characteristics"""
        
        # Download audio temporarily
        audio_path = await self._download_asset(asset.cdn_url)
        
        try:
            # Load audio
            y, sr = librosa.load(str(audio_path))
            
            # Get duration
            duration = librosa.get_duration(y=y, sr=sr)
            
            # Analyze tempo and beat
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # Analyze energy and dynamics
            rms = librosa.feature.rms(y=y)[0]
            energy_level = np.mean(rms)
            
            # Spectral analysis
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            brightness = np.mean(spectral_centroids) / sr
            
            # Detect mood
            mood = self._detect_audio_mood(tempo, energy_level, brightness)
            
            # Generate tags
            tags = self._generate_audio_tags(tempo, mood, energy_level)
            
            # Determine genre (simplified)
            genre = self._detect_music_genre(y, sr)
            
            analysis_result = {
                "duration": duration,
                "tempo": int(tempo),
                "energy_level": float(energy_level),
                "tags": tags,
                "categories": [genre, mood],
                "metadata": {
                    "sample_rate": sr,
                    "brightness": float(brightness),
                    "beats_count": len(beats),
                    "dynamic_range": float(np.std(rms)),
                    "mood": mood,
                    "genre": genre
                }
            }
            
            return analysis_result
            
        finally:
            # Cleanup
            audio_path.unlink()
    
    def _detect_audio_mood(
        self,
        tempo: float,
        energy: float,
        brightness: float
    ) -> str:
        """Detect mood of audio based on features"""
        
        for mood, criteria in self.music_moods.items():
            tempo_range = criteria.get("tempo", (0, 300))
            energy_range = criteria.get("energy", (0, 1))
            
            if (tempo_range[0] <= tempo <= tempo_range[1] and
                energy_range[0] <= energy <= energy_range[1]):
                return mood
        
        return "neutral"
    
    def _detect_music_genre(self, y: np.ndarray, sr: int) -> str:
        """Detect music genre (simplified)"""
        
        # In production, use a trained audio classification model
        # This is a simplified approach based on spectral features
        
        # Extract MFCCs
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfccs, axis=1)
        
        # Simple genre classification based on MFCC patterns
        if mfcc_mean[0] > 0:
            return "electronic"
        elif mfcc_mean[1] > 0:
            return "acoustic"
        else:
            return "mixed"
    
    # ========================================================================
    # IMAGE ANALYSIS
    # ========================================================================
    
    async def _analyze_image(self, asset: Asset) -> Dict[str, Any]:
        """Analyze image asset"""
        
        # Download image temporarily
        image_path = await self._download_asset(asset.cdn_url)
        
        try:
            # Open image
            image = Image.open(image_path)
            
            # Get basic info
            width, height = image.size
            format = image.format
            
            # Extract dominant colors
            dominant_colors = self._extract_dominant_colors([np.array(image)])
            
            # Detect content type
            content_type = self._detect_image_content(np.array(image))
            
            # Generate tags
            tags = [content_type, f"{width}x{height}", format.lower()]
            
            analysis_result = {
                "resolution": f"{width}x{height}",
                "format": format,
                "dominant_colors": dominant_colors,
                "tags": tags,
                "categories": [content_type],
                "metadata": {
                    "aspect_ratio": width / height,
                    "file_format": format,
                    "color_mode": image.mode
                }
            }
            
            return analysis_result
            
        finally:
            # Cleanup
            image_path.unlink()
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _extract_dominant_colors(
        self,
        frames: List[np.ndarray],
        n_colors: int = 5
    ) -> List[str]:
        """Extract dominant colors from frames"""
        
        from sklearn.cluster import KMeans
        
        # Sample pixels from all frames
        pixels = []
        
        for frame in frames:
            # Resize for faster processing
            small_frame = cv2.resize(frame, (100, 100))
            pixels.extend(small_frame.reshape(-1, 3))
        
        # Limit pixels
        pixels = np.array(pixels[:10000])
        
        # Cluster colors
        kmeans = KMeans(n_clusters=n_colors, random_state=42)
        kmeans.fit(pixels)
        
        # Get dominant colors
        colors = kmeans.cluster_centers_.astype(int)
        
        # Convert to hex
        hex_colors = []
        for color in colors:
            hex_color = '#{:02x}{:02x}{:02x}'.format(color[0], color[1], color[2])
            hex_colors.append(hex_color)
        
        return hex_colors
    
    def _generate_video_tags(
        self,
        scene_analysis: Dict[str, Any],
        motion_analysis: Dict[str, Any],
        video_info: Dict[str, Any]
    ) -> List[str]:
        """Generate relevant tags for video"""
        
        tags = []
        
        # Add scene-based tags
        tags.extend(scene_analysis["scene_types"])
        tags.extend(scene_analysis["categories"])
        
        # Add motion-based tags
        tags.append(f"{motion_analysis['motion_intensity']}_motion")
        
        # Add technical tags
        if video_info["fps"] >= 60:
            tags.append("60fps")
        
        if video_info["width"] >= 1920:
            tags.append("hd")
        
        if video_info["width"] >= 3840:
            tags.append("4k")
        
        # Add energy tags
        energy = motion_analysis["energy_level"]
        if energy > 0.7:
            tags.append("high_energy")
        elif energy < 0.3:
            tags.append("calm")
        
        return list(set(tags))
    
    def _generate_audio_tags(
        self,
        tempo: float,
        mood: str,
        energy: float
    ) -> List[str]:
        """Generate tags for audio"""
        
        tags = [mood]
        
        # Tempo-based tags
        if tempo >= 140:
            tags.append("fast")
        elif tempo >= 120:
            tags.append("upbeat")
        elif tempo <= 80:
            tags.append("slow")
        
        # Energy-based tags
        if energy > 0.7:
            tags.append("energetic")
        elif energy < 0.3:
            tags.append("ambient")
        
        # BPM tag
        tags.append(f"{int(tempo)}bpm")
        
        return tags
    
    async def _determine_content_rating(
        self,
        frames: List[np.ndarray]
    ) -> ContentRating:
        """Determine content rating for asset"""
        
        # In production, use content moderation API
        # This is a placeholder
        
        return ContentRating.GENERAL
    
    def _detect_image_content(self, image: np.ndarray) -> str:
        """Detect type of content in image"""
        
        # In production, use image classification model
        # This is a simplified approach
        
        mean_color = np.mean(image, axis=(0, 1))
        
        if mean_color[2] > mean_color[0]:  # Blue dominant
            return "abstract"
        elif mean_color[1] > mean_color[0]:  # Green dominant
            return "nature"
        else:
            return "general"
    
    async def _download_asset(self, url: str) -> Path:
        """Download asset temporarily for analysis"""
        
        import aiohttp
        import tempfile
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                content = await response.read()
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(content)
                    return Path(tmp.name)
    
    async def _update_asset_with_analysis(
        self,
        asset_id: int,
        analysis: Dict[str, Any]
    ):
        """Update asset record with analysis results"""
        
        async with AsyncSessionLocal() as db:
            update_data = {
                "tags": analysis.get("tags", []),
                "categories": analysis.get("categories", []),
                "duration": analysis.get("duration"),
                "resolution": analysis.get("resolution"),
                "tempo": analysis.get("tempo"),
                "energy_level": analysis.get("energy_level"),
                "dominant_colors": analysis.get("dominant_colors", []),
                "content_rating": analysis.get("content_rating", ContentRating.GENERAL),
                "metadata": {
                    **analysis.get("metadata", {}),
                    "analyzed_at": datetime.utcnow().isoformat()
                },
                "status": AssetStatus.ACTIVE
            }
            
            await db.execute(
                update(Asset)
                .where(Asset.id == asset_id)
                .values(**update_data)
            )
            
            await db.commit()

# Initialize service
asset_analysis_service = AssetAnalysisService()
