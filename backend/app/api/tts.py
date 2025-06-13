# backend/app/api/tts.py
"""
🎙️ REELS GENERATOR - Text-to-Speech API
Endpoints for voice synthesis with ElevenLabs and AWS Polly
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any, Optional
import logging
import json

from ..database import get_db
from ..models import User, Project, ProjectStatus
from ..schemas import (
    TTSRequest,
    TTSResponse,
    VoiceInfo,
    VoiceCloneRequest,
    ProjectResponse
)
from ..services.text_to_speech import tts_service, VoicePresets
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# TTS GENERATION ENDPOINTS
# ============================================================================

@router.post("/generate", response_model=TTSResponse)
async def generate_tts(
    request: TTSRequest,
    current_user: User = Depends(get_current_active_user)
) -> TTSResponse:
    """
    Generate text-to-speech audio
    
    Uses ElevenLabs by default, falls back to AWS Polly if needed.
    Returns S3 URL of the generated audio file.
    """
    
    try:
        logger.info(f"🎙️ Generating TTS for user {current_user.username} - Voice: {request.voice_id}")
        
        # Generate speech
        result = await tts_service.generate_speech(
            text=request.text,
            voice_id=request.voice_id,
            speed=request.speed
        )
        
        # Track usage
        if result["provider"] == "elevenlabs":
            # In production, track ElevenLabs character usage
            pass
        
        logger.info(f"✅ TTS generated successfully - Duration: {result['duration']}s")
        
        return TTSResponse(**result)
        
    except Exception as e:
        logger.error(f"💥 TTS generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text-to-speech generation failed. Please try again."
        )

@router.post("/generate-for-project/{project_id}", response_model=ProjectResponse)
async def generate_project_tts(
    project_id: int,
    voice_id: Optional[str] = None,
    speed: float = 1.0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Generate TTS for a project's script
    
    Automatically generates audio from the project's script and updates
    the project with the audio file path.
    """
    
    # Get project
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if not project.script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no script. Generate content first."
        )
    
    if project.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project already has audio. Delete existing audio first."
        )
    
    try:
        # Use project voice_id or provided one
        final_voice_id = voice_id or project.voice_id or "rachel"
        
        # Get recommended voice if not specified
        if final_voice_id == "auto":
            final_voice_id = await tts_service.get_recommended_voice(
                project.topic or "",
                project.target_audience or "",
                project.video_style or "general"
            )
        
        # Generate TTS
        logger.info(f"🎙️ Generating TTS for project {project_id}")
        result = await tts_service.generate_speech(
            text=project.script,
            voice_id=final_voice_id,
            speed=speed
        )
        
        # Update project
        project.audio_file_path = result["audio_url"]
        project.voice_id = final_voice_id
        
        await db.commit()
        await db.refresh(project)
        
        logger.info(f"✅ TTS generated for project {project_id} - Duration: {result['duration']}s")
        
        return project
        
    except Exception as e:
        logger.error(f"💥 Project TTS generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TTS generation failed for project"
        )

# ============================================================================
# VOICE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/voices", response_model=List[VoiceInfo])
async def list_available_voices(
    current_user: User = Depends(get_current_active_user)
) -> List[VoiceInfo]:
    """
    Get list of available voices
    
    Returns all available voices from both ElevenLabs and AWS Polly
    with their descriptions and preview URLs.
    """
    
    voices = []
    
    # Add mapped voices
    for voice_id, mapping in tts_service.voice_mappings.items():
        # Generate preview URL
        preview_url = await tts_service.preview_voice(voice_id)
        
        voices.append(VoiceInfo(
            voice_id=voice_id,
            name=voice_id.title(),
            description=mapping["description"],
            provider="both",  # Available in both services
            preview_url=preview_url
        ))
    
    # Get additional ElevenLabs voices if available
    if tts_service.elevenlabs_api_key:
        try:
            elevenlabs_voices = await tts_service.get_elevenlabs_voices()
            for voice in elevenlabs_voices[:5]:  # Limit to avoid too many
                if voice["voice_id"] not in [m["elevenlabs_id"] for m in tts_service.voice_mappings.values()]:
                    voices.append(VoiceInfo(
                        voice_id=voice["voice_id"],
                        name=voice["name"],
                        description=voice.get("labels", {}).get("description", "Custom voice"),
                        provider="elevenlabs",
                        preview_url=voice.get("preview_url", "")
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch ElevenLabs voices: {e}")
    
    return voices

@router.get("/voice/{voice_id}/preview")
async def preview_voice(
    voice_id: str,
    text: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Generate a preview of a specific voice
    
    Creates a short audio sample to preview how a voice sounds.
    """
    
    try:
        preview_url = await tts_service.preview_voice(voice_id, text)
        return {
            "voice_id": voice_id,
            "preview_url": preview_url,
            "text": text or "Hi there! This is a preview of my voice. I hope you like how I sound!"
        }
        
    except Exception as e:
        logger.error(f"💥 Voice preview failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice preview generation failed"
        )

@router.post("/voice/recommend")
async def recommend_voice(
    topic: str,
    target_audience: str,
    style: str = "general",
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get AI-recommended voice for content
    
    Suggests the best voice based on content characteristics.
    """
    
    try:
        recommended_voice = await tts_service.get_recommended_voice(
            topic, target_audience, style
        )
        
        # Get voice info
        voice_mapping = tts_service.voice_mappings.get(recommended_voice, {})
        
        return {
            "recommended_voice_id": recommended_voice,
            "reason": f"Based on your {style} content targeting {target_audience}",
            "voice_description": voice_mapping.get("description", ""),
            "alternatives": [
                vid for vid in tts_service.voice_mappings.keys() 
                if vid != recommended_voice
            ]
        }
        
    except Exception as e:
        logger.error(f"💥 Voice recommendation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice recommendation failed"
        )

# ============================================================================
# VOICE CLONING ENDPOINTS (PRO FEATURE)
# ============================================================================

@router.post("/voice/clone")
async def clone_voice(
    voice_name: str = Form(...),
    description: str = Form(""),
    audio_files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Clone a voice using audio samples (ElevenLabs Pro feature)
    
    Requires 1-5 audio samples of the voice to clone.
    Only available for premium users.
    """
    
    # Check if user is premium
    if current_user.subscription_plan != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice cloning is only available for premium users"
        )
    
    # Validate audio files
    if len(audio_files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 audio samples allowed"
        )
    
    try:
        # Read audio files
        audio_data = []
        for file in audio_files:
            if not file.content_type.startswith("audio/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {file.content_type}"
                )
            
            content = await file.read()
            audio_data.append(content)
        
        # Clone voice
        voice_id = await tts_service.clone_voice(
            voice_name=voice_name,
            audio_files=audio_data,
            description=description
        )
        
        logger.info(f"✅ Voice cloned successfully: {voice_id}")
        
        return {
            "voice_id": voice_id,
            "name": voice_name,
            "message": "Voice cloned successfully!"
        }
        
    except Exception as e:
        logger.error(f"💥 Voice cloning failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================================================
# USAGE & LIMITS ENDPOINTS
# ============================================================================

@router.get("/usage")
async def get_tts_usage(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get TTS usage statistics and limits
    
    Shows ElevenLabs character usage and remaining quota.
    """
    
    usage_data = {
        "elevenlabs": {
            "available": bool(tts_service.elevenlabs_api_key),
            "characters_used": 0,
            "characters_limit": 0,
            "characters_remaining": 0
        },
        "aws_polly": {
            "available": True,
            "characters_used": 0,
            "characters_limit": "unlimited"
        }
    }
    
    # Get ElevenLabs usage if available
    if tts_service.elevenlabs_api_key:
        try:
            elevenlabs_usage = await tts_service.get_elevenlabs_usage()
            subscription = elevenlabs_usage.get("subscription", {})
            
            usage_data["elevenlabs"] = {
                "available": True,
                "characters_used": subscription.get("character_count", 0),
                "characters_limit": subscription.get("character_limit", 0),
                "characters_remaining": subscription.get("character_limit", 0) - subscription.get("character_count", 0),
                "next_reset": subscription.get("next_character_count_reset_unix", 0)
            }
        except Exception as e:
            logger.error(f"Failed to fetch ElevenLabs usage: {e}")
    
    return usage_data

# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@router.post("/batch-generate")
async def batch_generate_tts(
    projects: List[int],
    voice_id: str = "rachel",
    speed: float = 1.0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate TTS for multiple projects
    
    Batch process TTS generation for efficiency.
    Maximum 10 projects per batch.
    """
    
    if len(projects) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 projects per batch"
        )
    
    results = {
        "successful": [],
        "failed": [],
        "skipped": []
    }
    
    for project_id in projects:
        try:
            # Get project
            result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.user_id == current_user.id
                )
            )
            project = result.scalar_one_or_none()
            
            if not project:
                results["failed"].append({
                    "project_id": project_id,
                    "error": "Project not found"
                })
                continue
            
            if not project.script:
                results["skipped"].append({
                    "project_id": project_id,
                    "reason": "No script"
                })
                continue
            
            if project.audio_file_path:
                results["skipped"].append({
                    "project_id": project_id,
                    "reason": "Audio already exists"
                })
                continue
            
            # Generate TTS
            tts_result = await tts_service.generate_speech(
                text=project.script,
                voice_id=voice_id,
                speed=speed
            )
            
            # Update project
            project.audio_file_path = tts_result["audio_url"]
            project.voice_id = voice_id
            
            results["successful"].append({
                "project_id": project_id,
                "duration": tts_result["duration"],
                "provider": tts_result["provider"]
            })
            
        except Exception as e:
            logger.error(f"Batch TTS failed for project {project_id}: {e}")
            results["failed"].append({
                "project_id": project_id,
                "error": str(e)
            })
    
    await db.commit()
    
    return {
        "summary": {
            "total": len(projects),
            "successful": len(results["successful"]),
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"])
        },
        "details": results
    }

# ============================================================================
# VOICE PRESETS
# ============================================================================

@router.get("/presets")
async def get_voice_presets(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get predefined voice presets for different content types
    
    Returns optimized voice settings for various styles.
    """
    
    return {
        "gaming": VoicePresets.GAMING,
        "educational": VoicePresets.EDUCATIONAL,
        "business": VoicePresets.BUSINESS,
        "storytelling": VoicePresets.STORYTELLING
    }

@router.post("/apply-preset/{preset_name}")
async def apply_voice_preset(
    preset_name: str,
    text: str,
    current_user: User = Depends(get_current_active_user)
) -> TTSResponse:
    """
    Generate TTS using a predefined preset
    
    Applies optimized settings for the content type.
    """
    
    presets = {
        "gaming": VoicePresets.GAMING,
        "educational": VoicePresets.EDUCATIONAL,
        "business": VoicePresets.BUSINESS,
        "storytelling": VoicePresets.STORYTELLING
    }
    
    if preset_name not in presets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset not found. Available: {list(presets.keys())}"
        )
    
    preset = presets[preset_name]
    
    try:
        result = await tts_service.generate_speech(
            text=text,
            voice_id=preset["voice_id"],
            speed=preset["speed"]
        )
        
        return TTSResponse(**result)
        
    except Exception as e:
        logger.error(f"💥 Preset TTS generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TTS generation with preset failed"
        )
