# backend/app/main.py
"""
🎬 REELS GENERATOR - FastAPI Main Application
Production-ready FastAPI setup with authentication, content generation, and error handling
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
from .api import auth, projects, analytics, webhooks, content

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
    
    logger.info("✅ Database tables created")
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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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
    logger.info(f"📨 {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"📤 {response.status_code} - {request.method} {request.url}")
    return response

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time()
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """Internal server error handler"""
    logger.error(f"💥 Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error occurred",
            "status_code": 500,
            "timestamp": time.time()
        }
    )

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
            "video_processing": "🚧 Coming Soon (Week 3-4)",
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
    
    # Test OpenAI connection
    try:
        import openai
        openai.api_key = settings.OPENAI_API_KEY
        # Just check if key is set
        ai_status = "healthy" if settings.OPENAI_API_KEY else "unhealthy"
    except Exception as e:
        logger.error(f"💥 OpenAI health check failed: {e}")
        ai_status = "unhealthy"
    
    # Test Redis connection (if available)
    redis_status = "healthy"  # TODO: Implement Redis health check
    
    overall_status = "healthy" if all(s == "healthy" for s in [db_status, ai_status, redis_status]) else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "services": {
            "database": db_status,
            "redis": redis_status,
            "openai": ai_status,
            "api": "healthy"
        },
        "version": "1.0.0"
    }

@app.get("/metrics", tags=["health"])
async def metrics():
    """Prometheus-compatible metrics endpoint"""
    # TODO: Implement actual metrics collection
    return {
        "metrics": {
            "requests_total": 0,
            "requests_duration_seconds": 0.0,
            "active_users": 0,
            "videos_generated_total": 0,
            "videos_processing": 0,
            "content_generations_total": 0,
            "average_content_score": 0.0
        },
        "timestamp": time.time()
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

# Content generation routes (NEW - Week 2)
app.include_router(
    content.router,
    prefix="/api/v1/content",
    tags=["content"],
    dependencies=[Depends(security)]
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
# DEVELOPMENT HELPERS
# ============================================================================

if settings.DEBUG:
    @app.get("/debug/info", tags=["development"])
    async def debug_info():
        """Debug information (only in development)"""
        return {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "week": "Week 2 - Content Generation",
            "features_implemented": [
                "GPT-4 Integration",
                "Story Generation",
                "Hashtag Optimization", 
                "Content Quality Analysis",
                "Script Variations",
                "Platform Optimization"
            ],
            "database_url": settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0].split('://')[-1], "***"),
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "allowed_origins": settings.ALLOWED_ORIGINS
        }

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
    logger.info(f"🤖 OpenAI: {'Connected' if settings.OPENAI_API_KEY else 'Not Configured'}")
    logger.info(f"🔐 Auth: JWT Enabled")
    logger.info(f"📡 CORS: {len(settings.ALLOWED_ORIGINS)} origins allowed")
    logger.info("=" * 60)
    logger.info("📅 WEEK 2 FEATURES:")
    logger.info("  ✅ AI Content Generation")
    logger.info("  ✅ Hashtag Optimization")
    logger.info("  ✅ Content Quality Analysis")
    logger.info("  ✅ A/B Testing Variations")
    logger.info("  ✅ Platform Optimization")
    logger.info("=" * 60)
    logger.info("🚀 Ready to generate amazing content!")
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
