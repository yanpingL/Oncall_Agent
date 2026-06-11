"""File upload API module"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.vector_index_service import vector_index_service
from loguru import logger

router = APIRouter()

# Storage path after file upload
UPLOAD_DIR = Path("./uploads")
# Supported file types
ALLOWED_EXTENSIONS = ["txt", "md"]
# Maximum supported size for one file
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file and automatically create vector index

    Args:
        file: uploaded file

    Returns:
        JSONResponse: upload result
    """
    try:
        # 1. Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="File name cannot be empty")

        # 2. Normalize file name by removing spaces and handling Windows uploads
        safe_filename = _sanitize_filename(file.filename)

        # 3. Validate file extension
        file_extension = _get_file_extension(safe_filename)
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format; only supported: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # 4. Create upload directory
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # 5. Save file
        file_path = UPLOAD_DIR / safe_filename

        # If file already exists, delete the old file to overwrite it
        if file_path.exists():
            logger.info(f"File already exists and will be overwritten: {file_path}")
            file_path.unlink()

        # Read and save file content
        content = await file.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds limit (max {MAX_FILE_SIZE} bytes)")

        file_path.write_bytes(content)

        logger.info(f"File uploaded successfully: {file_path}")

        # 5. Automatically create vector index
        try:
            logger.info(f"Starting vector index creation for uploaded file: {file_path}")
            vector_index_service.index_single_file(str(file_path))
            logger.info(f"Vector index created successfully: {file_path}")
        except Exception as e:
            logger.error(f"Vector index creation failed: {file_path}, error: {e}")
            # Note: even if indexing fails, file upload still succeeds; only error logs are recorded

        # 6. Return response
        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "filename": safe_filename,
                    "file_path": str(file_path),
                    "size": len(content),
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


@router.post("/index_directory")
async def index_directory(directory_path: str = None):
    """
    Index all files in the specified directory

    Args:
        directory_path: directory path, optional; defaults to uploads directory

    Returns:
        JSONResponse: Indexing result
    """
    try:
        logger.info(f"Starting directory indexing: {directory_path or 'uploads'}")

        # Run indexing
        result = vector_index_service.index_directory(directory_path)

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success" if result.success else "partial_success",
                "data": result.to_dict(),
            },
        )

    except Exception as e:
        logger.error(f"Directory indexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Directory indexing failed: {e}")


def _get_file_extension(filename: str) -> str:
    """
    Get file extension

    Args:
        filename: file name

    Returns:
        str: extension, lowercase without dot
    """
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[1].lower()
    return ""


def _sanitize_filename(filename: str) -> str:
    """
    Normalize file name by removing spaces and special characters

    Args:
        filename: original file name

    Returns:
        str: normalized file name
    """
    # Remove spaces
    sanitized = filename.replace(" ", "_")
    # Remove other potentially problematic characters
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        sanitized = sanitized.replace(char, "_")
    return sanitized
