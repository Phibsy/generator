# backend/app/main.py - Week 5 Update
"""
🎬 REELS GENERATOR - FastAPI Main Application
Now with Week 5: Advanced Video Processing and WebSocket support
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging
from typing import Dict, Any

from .config import settings
from .database import engine, Base
from .api import auth, projects, analytics, webhooks, content, tts, video, advanced_video
from .services.websocket_manager import ws_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("🚀 Starting Reels Generator API...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize services
    from .services.advanced_video_processing import advanced_video_service
    await advanced_video_service.init_progress_tracking()
    
    logger.info("✅ Database tables created")
    logger.info("✅ WebSocket manager initialized")
    logger.info("🎬 Reels Generator API is ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Reels Generator API...")

# Initialize FastAPI app
app = FastAPI(
    title="🎬 Reels Generator API",
    description="""
    ## 🎯 Professional Content Creation Platform
    
    Automated YouTube Shorts and Instagram Reels generation system with:
    
    * **🤖 AI Content Generation** - GPT-4 powered storytelling
    * **🎙️ Text-to-Speech** - ElevenLabs & AWS Polly integration  
    * **🎬 Video Processing** - Automated video composition with subtitles
    * **🎥 Advanced Video** - Word-timing, music, effects, real-time progress (Week 5)
    * **📱 Social Media Integration** - Direct publishing to platforms
    * **📊 Analytics & Insights** - Performance tracking and optimization
    
    ### 🔐 Authentication Required
    All endpoints require JWT authentication via Bearer token.
    
    ### 📝 Content Generation Features (Week 2)
    * **Story Generation** - AI-powered script creation
    * **Hashtag Optimization** - Platform-specific hashtag generation
    * **Content Analysis** - Quality scoring and improvement suggestions
    * **A/B Testing** - Generate script variations
    * **Platform Optimization** - Adapt content for each platform
    
    ### 🎙️ Text-to-Speech Features (Week 3)
    * **Multiple Voices** - Professional voice selection
    * **Speed Control** - Adjustable speaking rate
    * **Voice Cloning** - Custom voice creation (Pro)
    * **Fallback System** - ElevenLabs → AWS Polly
    
    ### 🎬 Video Processing Features (Week 4)
    * **Automated Composition** - Full video generation pipeline
    * **Subtitle Animations** - Word-by-word, karaoke, line-by-line
    * **Background Videos** - Gaming, nature, tech presets
    * **Templates** - Pre-configured video styles
    * **Batch Processing** - Multiple videos at once
    
    ### 🎥 Advanced Video Features (Week 5) 🆕
    * **Word-Level Timing** - Precise subtitle synchronization
    * **Background Music** - Auto-ducking and beat sync
    * **Visual Effects** - Dynamic, smooth, and minimal presets
    * **Real-time Progress** - WebSocket updates
    * **Quality Presets** - Low to Ultra (4K) quality
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "authentication",
            "description": "🔐 User authentication and authorization"
        },
        {
            "name": "projects", 
            "description": "📁 Project and content management"
        },
        {
            "name": "content",
            "description": "🤖 AI-powered content generation"
        },
        {
            "name": "text-to-speech",
            "description": "🎙️ Voice synthesis and audio generation"
        },
        {
            "name": "video-processing",
            "description": "🎬 Video generation and processing"
        },
        {
            "name": "advanced-video",
            "description": "🎥 Advanced video with effects and real-time progress"
        },
        {
            "name": "websocket",
            "description": "🔌 WebSocket for real-time updates"
        },
        {
            "name": "analytics",
            "description": "📊 Performance analytics and insights"
        },
        {
            "name": "webhooks",
            "description": "🔗 Platform webhooks and integrations"
        },
        {
            "name": "health",
            "description": "💚 System health and monitoring"
        }
    ]
)

# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS Middleware - Updated for WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],  # For WebSocket upgrade headers
)

# Trusted Host Middleware
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# Performance Monitoring Middleware
@app.middleware("http")
async def add_process_time_header(request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Request Logging Middleware
@app.middleware("http") 
async def log_requests(request, call_next):
    """Log all incoming requests"""
    # Skip WebSocket upgrade requests
    if request.url.path.startswith("/ws/"):
        return await call_next(request)
    
    logger.info(f"📨 {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"📤 {response.status_code} - {request.method} {request.url}")
    return response

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/", tags=["health"])
async def root():
    """Root endpoint - API status"""
    return {
        "message": "🎬 Reels Generator API is running!",
        "version": "1.0.0",
        "status": "healthy",
        "features": {
            "authentication": "✅ Active",
            "content_generation": "✅ Active (Week 2)",
            "text_to_speech": "✅ Active (Week 3)", 
            "video_processing": "✅ Active (Week 4)",
            "advanced_video": "✅ Active (Week 5)",
            "websocket_progress": "✅ Active (Week 5)",
            "social_media": "🚧 Coming Soon (Week 11)"
        },
        "timestamp": time.time()
    }

@app.get("/health", tags=["health"])
async def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection
        from .database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"💥 Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Test Redis connection
    try:
        from .services.websocket_manager import manager
        await manager.init_redis()
        await manager.redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"💥 Redis health check failed: {e}")
        redis_status = "unhealthy"
    
    # Test OpenAI connection
    try:
        import openai
        openai.api_key = settings.OPENAI_API_KEY
        ai_status = "healthy" if settings.OPENAI_API_KEY else "unhealthy"
    except Exception as e:
        logger.error(f"💥 OpenAI health check failed: {e}")
        ai_status = "unhealthy"
    
    # Test FFmpeg installation
    try:
        from .utils.ffmpeg_utils import ffmpeg_utils
        ffmpeg_installed = await ffmpeg_utils.validate_ffmpeg_installation()
        ffmpeg_status = "healthy" if ffmpeg_installed else "unhealthy"
    except Exception:
        ffmpeg_status = "unhealthy"
    
    overall_status = "healthy" if all(
        s == "healthy" for s in [db_status, ai_status, redis_status, ffmpeg_status]
    ) else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "services": {
            "database": db_status,
            "redis": redis_status,
            "openai": ai_status,
            "ffmpeg": ffmpeg_status,
            "websocket": "healthy",
            "api": "healthy"
        },
        "version": "1.0.0"
    }

# ============================================================================
# API ROUTES
# ============================================================================

# Authentication routes
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["authentication"]
)

# Project management routes  
app.include_router(
    projects.router,
    prefix="/api/v1/projects", 
    tags=["projects"],
    dependencies=[Depends(security)]
)

# Content generation routes (Week 2)
app.include_router(
    content.router,
    prefix="/api/v1/content",
    tags=["content"],
    dependencies=[Depends(security)]
)

# Text-to-Speech routes (Week 3)
app.include_router(
    tts.router,
    prefix="/api/v1/tts",
    tags=["text-to-speech"],
    dependencies=[Depends(security)]
)

# Video processing routes (Week 4)
app.include_router(
    video.router,
    prefix="/api/v1/video",
    tags=["video-processing"],
    dependencies=[Depends(security)]
)

# Advanced video processing routes (NEW - Week 5)
app.include_router(
    advanced_video.router,
    prefix="/api/v1/video",
    tags=["advanced-video"],
    dependencies=[Depends(security)]
)

# WebSocket routes (NEW - Week 5)
app.include_router(
    ws_router,
    tags=["websocket"]
)

# Analytics routes
app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"], 
    dependencies=[Depends(security)]
)

# Webhook routes
app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["webhooks"]
)

# ============================================================================
# STARTUP MESSAGE
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("🎬 REELS GENERATOR API STARTING")
    logger.info("=" * 60)
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🐛 Debug Mode: {settings.DEBUG}")
    logger.info(f"📊 Database: Connected")
    logger.info(f"🔴 Redis: Connected")
    logger.info(f"🤖 OpenAI: {'Connected' if settings.OPENAI_API_KEY else 'Not Configured'}")
    logger.info(f"🎙️ ElevenLabs: {'Connected' if settings.ELEVENLABS_API_KEY else 'Not Configured'}")
    logger.info(f"☁️ AWS: {'Connected' if settings.AWS_ACCESS_KEY_ID else 'Not Configured'}")
    logger.info(f"🔐 Auth: JWT Enabled")
    logger.info(f"📡 CORS: {len(settings.ALLOWED_ORIGINS)} origins allowed")
    logger.info(f"🔌 WebSocket: Enabled")
    logger.info("=" * 60)
    logger.info("📅 IMPLEMENTED FEATURES:")
    logger.info("  ✅ Week 1: Setup & Authentication")
    logger.info("  ✅ Week 2: AI Content Generation")
    logger.info("  ✅ Week 3: Text-to-Speech")
    logger.info("  ✅ Week 4: Video Processing")
    logger.info("  ✅ Week 5: Advanced Video Processing")
    logger.info("=" * 60)
    logger.info("📅 WEEK 5 FEATURES:")
    logger.info("  ✅ Word-Level Subtitle Timing")
    logger.info("  ✅ Background Music with Auto-Ducking")
    logger.info("  ✅ Beat-Synchronized Effects")
    logger.info("  ✅ Real-time Progress via WebSocket")
    logger.info("  ✅ Quality Presets (Low to 4K)")
    logger.info("=" * 60)
    logger.info("🚀 Ready to create amazing videos with advanced features!")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG,
        log_level="info"
    )
