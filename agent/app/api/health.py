"""Health check API"""

from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.config import config
from app.core.milvus_client import milvus_manager
from loguru import logger

router = APIRouter()


@router.get("/live")
async def liveness_check():
    """Lightweight liveness check for load balancers and container health checks."""
    return {
        "code": 200,
        "message": "Service is alive",
        "data": {
            "service": config.app_name,
            "version": config.app_version,
            "status": "alive",
        },
    }


@router.get("/health")
async def health_check():
    
    """Health check API
    Check service status and database connection status
    
    Returns:
        JSONResponse: Health check result
    """
    # Check basic service status
    health_data: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "service": config.app_name,
        "version": config.app_version,
        "status": "healthy"
    }
    
    # Check Milvus connection status
    try:
        milvus_healthy = milvus_manager.health_check()
        milvus_status: str = "connected" if milvus_healthy else "disconnected"
        milvus_message: str = "Milvus connection normal" if milvus_healthy else "Milvus connection abnormal"
        health_data["milvus"] = {
            "status": milvus_status,
            "message": milvus_message
        }
    except Exception as e:
        logger.warning(f"Milvus health check failed: {e}")
        health_data["milvus"] = {
            "status": "error",
            "message": f"Milvus check failed: {str(e)}"
        }
    
    # Determine overall health status
    overall_status = "healthy"
    status_code = 200
    
    # If Milvus is unavailable, the service is unavailable
    if health_data["milvus"]["status"] != "connected":
        overall_status = "unhealthy"
        status_code = 503
        health_data["error"] = "Database unavailable"
    
    health_data["status"] = overall_status
    
    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "message": "Service is running normally" if overall_status == "healthy" else "Service unavailable",
            "data": health_data
        }
    )
