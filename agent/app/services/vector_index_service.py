
"""Vector indexing service module"""

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, Optional

from loguru import logger

from app.services.document_splitter_service import document_splitter_service
from app.services.vector_store_manager import vector_store_manager


class IndexingResult:
    """Indexing result class"""

    def __init__(self):
        self.success = False
        self.directory_path = ""
        self.total_files = 0
        self.success_count = 0
        self.fail_count = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error_message = ""
        self.failed_files: Dict[str, str] = {}

    def increment_success_count(self):
        """Increment success count"""
        self.success_count += 1

    def increment_fail_count(self):
        """Increment failure count"""
        self.fail_count += 1

    def add_failed_file(self, file_path: str, error: str):
        """Add failed file"""
        self.failed_files[file_path] = error

    def get_duration_ms(self) -> int:
        """Get duration in milliseconds"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "directory_path": self.directory_path,
            "total_files": self.total_files,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "duration_ms": self.get_duration_ms(),
            "error_message": self.error_message,
            "failed_files": self.failed_files,
        }


class VectorIndexService:
    """Vector indexing service that reads files, generates vectors, and stores them in Milvus"""

    def __init__(self):
        """Initialize vector indexing service"""
        self.upload_path = "./uploads"
        logger.info("Vector indexing service initialized")

    def index_directory(self, directory_path: Optional[str] = None) -> IndexingResult:
        """
        Index all files in the specified directory

        Args:
            directory_path: Directory path, optional; defaults to the configured upload directory

        Returns:
            IndexingResult: Indexing result
        """
        result = IndexingResult()
        result.start_time = datetime.now()

        try:
            # Use the specified directory or default upload directory
            target_path = directory_path if directory_path else self.upload_path
            dir_path = Path(target_path).resolve()

            if not dir_path.exists() or not dir_path.is_dir():
                raise ValueError(f"Directory does not exist or is not valid: {target_path}")

            result.directory_path = str(dir_path)

            # Get all supported files
            files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md"))

            if not files:
                logger.warning(f"No supported files found in directory: {target_path}")
                result.total_files = 0
                result.success = True
                result.end_time = datetime.now()
                return result

            result.total_files = len(files)
            logger.info(f"Starting directory indexing: {target_path}, found {len(files)} files")

            # Iterate and index each file
            for file_path in files:
                try:
                    self.index_single_file(str(file_path))
                    result.increment_success_count()
                    logger.info(f"✓ File indexed successfully: {file_path.name}")
                except Exception as e:
                    result.increment_fail_count()
                    result.add_failed_file(str(file_path), str(e))
                    logger.error(f"✗ File indexing failed: {file_path.name}, error: {e}")

            result.success = result.fail_count == 0
            result.end_time = datetime.now()

            logger.info(
                f"Directory indexing completed: total={result.total_files}, "
                f"success={result.success_count}, failed={result.fail_count}"
            )

            return result

        except Exception as e:
            logger.error(f"Directory indexing failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.end_time = datetime.now()
            return result

    def index_single_file(self, file_path: str):
        """
        Index a single file using the new LangChain splitter

        Args:
            file_path: File path

        Raises:
            ValueError: Raised when the file does not exist
            RuntimeError: Raised when indexing fails
        """
        path = Path(file_path).resolve()

        if not path.exists() or not path.is_file():
            raise ValueError(f"File does not exist: {file_path}")

        logger.info(f"Starting file indexing: {path}")

        try:
            # 1. Read file content
            content = path.read_text(encoding="utf-8")
            logger.info(f"Read file: {path}, content length: {len(content)} characters")

            # 2. Delete old data for this file if it exists
            normalized_path = path.as_posix()
            vector_store_manager.delete_by_source(normalized_path)

            # 3. Use the new document splitter
            documents = document_splitter_service.split_document(content, normalized_path)
            logger.info(f"Document splitting completed: {file_path} -> {len(documents)} chunks")

            # 4. Add documents to vector store
            if documents:
                vector_store_manager.add_documents(documents)
                logger.info(f"File indexing completed: {file_path}, total {len(documents)} chunks")
            else:
                logger.warning(f"File content is empty or cannot be split: {file_path}")

        except Exception as e:
            logger.error(f"File indexing failed: {file_path}, error: {e}")
            raise RuntimeError(f"File indexing failed: {e}") from e

    def index_aiops_report(self, report: str, session_id: str) -> str:
        """
        Save the final AIOps diagnosis report as Markdown and write it to the vector knowledge base.

        Args:
            report: Markdown report generated by the AIOps Agent
            session_id: Session ID used to generate a traceable file name

        Returns:
            str: Saved and indexed Markdown file path
        """
        if not report or not report.strip():
            raise ValueError("AIOps diagnosis report cannot be empty")

        created_at = datetime.now().isoformat(timespec="seconds")
        safe_session_id = self._sanitize_filename_part(session_id or "default")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_dir = Path(self.upload_path) / "generated_reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        file_path = report_dir / f"aiops_report_{safe_session_id}_{timestamp}.md"
        markdown_content = self._build_aiops_report_markdown(
            report=report,
            session_id=session_id,
            created_at=created_at,
        )

        file_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"AIOps diagnosis report saved as Markdown: {file_path}")

        self.index_single_file(str(file_path))
        return str(file_path)

    def _build_aiops_report_markdown(
        self,
        report: str,
        session_id: str,
        created_at: str,
    ) -> str:
        """Add lightweight metadata to generated reports while preserving the Markdown body."""
        metadata = (
            "---\n"
            "document_type: aiops_report\n"
            "source: aiops_agent\n"
            f"session_id: {session_id or 'default'}\n"
            f"created_at: {created_at}\n"
            "---\n\n"
        )
        return metadata + report.strip() + "\n"

    def _sanitize_filename_part(self, value: str) -> str:
        """Generate a string suitable as a file-name segment."""
        sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
        sanitized = sanitized.strip("_")
        return sanitized[:80] or "default"


# Global singleton
vector_index_service = VectorIndexService()
