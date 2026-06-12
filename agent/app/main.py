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
from app.core.metrics import metrics_middleware, metrics_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Run on startup
    logger.info("=" * 60)
    logger.info(f"🚀 {config.app_name} v{config.app_version} starting...")
    logger.info(f"📝 Environment: {'development' if config.debug else 'production'}")
    logger.info(f"🌐 Listening address: http://{config.host}:{config.port}")
    logger.info(f"📚 API docs: http://{config.host}:{config.port}/docs")
    
    # Connect Milvus when configured. In cloud deployments this can be disabled
    # during the first backend rollout and re-enabled after the vector DB is ready.
    if config.milvus_connect_on_startup:
        logger.info("🔌 Connecting to Milvus...")
        milvus_manager.connect()
        logger.info("✅ Milvus connected successfully")
    else:
        logger.warning("Milvus startup connection is disabled; vector features require Milvus later")
    
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
app.middleware("http")(metrics_middleware)

# Register routes
app.include_router(health.router, tags=["Health check"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(file.router, prefix="/api", tags=["File management"])
app.include_router(aiops.router, prefix="/api", tags=["AIOps operations"])

# Mount static files only when the frontend bundle is present.
static_dir = "static"
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """Return homepage"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isdir(static_dir) and os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": f"Welcome to {config.app_name} API",
        "version": config.app_version,
        "docs": "/docs"
    }


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return metrics_response()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )
