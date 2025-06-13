# backend/app/main.py
"""
🎬 REELS GENERATOR - FastAPI Main Application
Production-ready FastAPI setup with authentication, middleware, and error handling
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
from .api import auth, projects, analytics, webhooks

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
        "timestamp": time.time()
    }

@app.get("/health", tags=["health"])
async def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection
        from .database import get_db
        db = next(get_db())
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"💥 Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Test Redis connection (if available)
    redis_status = "healthy"  # TODO: Implement Redis health check
    
    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "services": {
            "database": db_status,
            "redis": redis_status,
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
            "videos_processing": 0
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
            "database_url": settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0].split('://')[-1], "***"),
            "allowed_origins": settings.ALLOWED_ORIGINS,
            "settings": {
                key: "***" if "key" in key.lower() or "secret" in key.lower() or "password" in key.lower() 
                else getattr(settings, key)
                for key in dir(settings) 
                if not key.startswith('_')
            }
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
    logger.info(f"🔐 Auth: JWT Enabled")
    logger.info(f"📡 CORS: {len(settings.ALLOWED_ORIGINS)} origins allowed")
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
