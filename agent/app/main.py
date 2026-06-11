"""FastAPI app entry point

Main application configuring routes, middleware, static files, etc.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.config import config
from loguru import logger
from app.api import chat, health, file, aiops
from app.core.milvus_client import milvus_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Run on startup
    logger.info("=" * 60)
    logger.info(f"🚀 {config.app_name} v{config.app_version} starting...")
    logger.info(f"📝 Environment: {'development' if config.debug else 'production'}")
    logger.info(f"🌐 Listening address: http://{config.host}:{config.port}")
    logger.info(f"📚 API docs: http://{config.host}:{config.port}/docs")
    
    # Connect Milvus
    logger.info("🔌 Connecting to Milvus...")
    milvus_manager.connect()
    logger.info("✅ Milvus connected successfully")
    
    logger.info("=" * 60)
    
    yield
    
    # Run on shutdown
    logger.info("🔌 Closing Milvus connection...")
    milvus_manager.close()
    logger.info(f"👋 {config.app_name} closed")


# Create FastAPI app
app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="LangChain-based intelligent on-call operations system",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production should restrict concrete domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, tags=["Health check"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(file.router, prefix="/api", tags=["File management"])
app.include_router(aiops.router, prefix="/api", tags=["AIOps operations"])

# Mount static files
static_dir = "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """Return homepage"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": f"Welcome to {config.app_name} API",
        "version": config.app_version,
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )
