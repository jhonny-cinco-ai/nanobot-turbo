"""Unified document processor with local/cloud fallback."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from nanofolks.config.schema import DocumentToolsConfig
from nanofolks.documents.complexity_analyzer import PDFComplexityAnalyzer
from nanofolks.utils.helpers import ensure_dir, safe_filename


@dataclass
class ProcessingResult:
    """Result of document processing."""
    success: bool
    method: str  # "local", "markdown_new", "fallback"
    content: str | None
    title: str | None = None
    tokens: int | None = None
    error: str | None = None
    complexity: dict | None = None
    metadata: dict | None = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "method": self.method,
            "content": self.content,
            "title": self.title,
            "tokens": self.tokens,
            "error": self.error,
            "complexity": self.complexity,
            "metadata": self.metadata
        }


class UnifiedDocumentProcessor:
    """
    Unified document processor with local processing and markdown.new fallback.
    
    Processing strategy:
    1. Detect file type
    2. If PDF: analyze complexity
       - Simple: use local pypdf
       - Complex: try markdown.new if enabled
    3. If unsupported format: use markdown.new if enabled
    4. Otherwise: return error
    """
    
    # File types supported by markdown.new
    MARKDOWN_NEW_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
        "application/vnd.oasis.opendocument.text",  # ODT
        "application/vnd.oasis.opendocument.spreadsheet",  # ODS
        "application/vnd.apple.numbers",  # Apple Numbers
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
        "text/csv",
        "application/json",
        "application/xml",
        "text/html",
        "text/plain",
    }
    
    def __init__(
        self,
        config: DocumentToolsConfig,
        base_dir: Path | None = None,
        enable_markdown_new: bool = True,
        complexity_thresholds: dict | None = None,
    ):
        self.config = config
        self.base_dir = base_dir
        self.enable_markdown_new = enable_markdown_new
        
        # Initialize complexity analyzer
        self.complexity_analyzer = PDFComplexityAnalyzer(complexity_thresholds)
        
        # Try to import local processor
        self._local_processor = None
        self._try_import_local_processor()
    
    def _try_import_local_processor(self) -> None:
        """Try to import the local document processor."""
        try:
            from nanofolks.documents.processor import DocumentProcessor
            if self.base_dir:
                self._local_processor = DocumentProcessor(self.base_dir, self.config)
        except ImportError:
            logger.warning("Local document processor not available")
    
    async def process(
        self,
        file_path: str,
        source_url: str | None = None,
    ) -> ProcessingResult:
        """
        Process a document with appropriate method.
        
        Args:
            file_path: Path to local file OR URL if source_url provided
            source_url: Optional URL if file is remote
            
        Returns:
            ProcessingResult with content and metadata
        """
        # Determine if we have a URL or local path
        if source_url:
            url = source_url
        elif file_path.startswith(("http://", "https://")):
            url = file_path
            file_path = None
        else:
            url = None
        
        # Detect file type
        mime_type = self._detect_mime_type(file_path, url)
        
        logger.debug(f"Processing document: {file_path or url}, type: {mime_type}")
        
        # Process based on type
        if mime_type == "application/pdf":
            return await self._process_pdf(file_path, url)
        elif mime_type in self.MARKDOWN_NEW_TYPES:
            return await self._process_markdown_new(url)
        elif mime_type == "text/plain" and file_path:
            return await self._process_local_text(file_path)
        else:
            return ProcessingResult(
                success=False,
                method="none",
                content=None,
                error=f"Unsupported file type: {mime_type}. Supported: PDF, DOCX, XLSX, Images, CSV, JSON, etc."
            )
    
    async def _process_pdf(
        self,
        file_path: str | None,
        url: str | None
    ) -> ProcessingResult:
        """Process PDF - local or cloud based on complexity."""
        
        # Try local first
        if file_path:
            # Analyze complexity
            complexity = self.complexity_analyzer.analyze(file_path)
            
            if complexity and not complexity.is_complex:
                # Simple PDF - use local processing
                result = self._process_pdf_locally(file_path)
                if result.success:
                    result.complexity = complexity.to_dict()
                    return result
            
            # Complex PDF or local failed
            if complexity:
                logger.info(
                    f"PDF is complex ({complexity.fallback_reason}), "
                    f"trying markdown.new"
                )
        
        # Try markdown.new if enabled
        if self.enable_markdown_new and url:
            result = await self._process_markdown_new(url)
            if result.success:
                if complexity:
                    result.complexity = complexity.to_dict()
                return result
        
        # All methods failed
        return ProcessingResult(
            success=False,
            method="all_failed",
            content=None,
            error="Failed to process PDF with all methods",
            complexity=complexity.to_dict() if complexity else None
        )
    
    def _process_pdf_locally(self, file_path: str) -> ProcessingResult:
        """Process PDF locally using pypdf."""
        
        if not self._local_processor:
            return ProcessingResult(
                success=False,
                method="local",
                content=None,
                error="Local processor not available"
            )
        
        try:
            results = self._local_processor.process_pdfs(
                [file_path],
                room_id="temp",
                session_metadata={}
            )
            
            if results:
                digest = results[0]
                return ProcessingResult(
                    success=True,
                    method="local",
                    content=digest.text_path,  # Return path to extracted text
                    title=digest.filename,
                    metadata=digest.to_dict()
                )
            else:
                return ProcessingResult(
                    success=False,
                    method="local",
                    content=None,
                    error="No results from local processor"
                )
                
        except Exception as e:
            logger.warning(f"Local PDF processing failed: {e}")
            return ProcessingResult(
                success=False,
                method="local",
                content=None,
                error=str(e)
            )
    
    async def _process_markdown_new(self, url: str) -> ProcessingResult:
        """Process file using markdown.new API."""
        
        if not url:
            return ProcessingResult(
                success=False,
                method="markdown_new",
                content=None,
                error="URL required for markdown.new conversion"
            )
        
        try:
            from nanofolks.agent.tools.markdown_convert import MarkdownNewTool
            
            tool = MarkdownNewTool()
            result = await tool.execute(url=url)
            data = json.loads(result)
            
            if data.get("success"):
                return ProcessingResult(
                    success=True,
                    method="markdown_new",
                    content=data.get("content"),
                    title=data.get("title"),
                    tokens=data.get("tokens"),
                    metadata={"url": url, "method": data.get("method")}
                )
            else:
                return ProcessingResult(
                    success=False,
                    method="markdown_new",
                    content=None,
                    error=data.get("error", "Conversion failed")
                )
                
        except Exception as e:
            logger.warning(f"markdown.new processing failed: {e}")
            return ProcessingResult(
                success=False,
                method="markdown_new",
                content=None,
                error=str(e)
            )
    
    async def _process_local_text(self, file_path: str) -> ProcessingResult:
        """Process plain text file locally."""
        
        try:
            path = Path(file_path)
            content = path.read_text(encoding="utf-8")
            
            return ProcessingResult(
                success=True,
                method="local",
                content=content,
                title=path.name,
                metadata={"path": str(path)}
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                method="local",
                content=None,
                error=str(e)
            )
    
    def _detect_mime_type(self, file_path: str | None, url: str | None) -> str:
        """Detect MIME type from file path or URL."""
        
        import mimetypes
        
        # Try from file path
        if file_path:
            mime, _ = mimetypes.guess_type(file_path)
            if mime:
                return mime
        
        # Try from URL
        if url:
            # Common extensions
            ext_map = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".csv": "text/csv",
                ".json": "application/json",
                ".xml": "application/xml",
                ".html": "text/html",
                ".htm": "text/html",
                ".txt": "text/plain",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
            }
            
            path = Path(url)
            ext = path.suffix.lower()
            if ext in ext_map:
                return ext_map[ext]
        
        return "application/octet-stream"


def detect_file_type(file_path: str | None = None, url: str | None = None) -> str:
    """
    Convenience function to detect file type.
    
    Args:
        file_path: Path to local file
        url: URL to remote file
        
    Returns:
        MIME type string
    """
    processor = UnifiedDocumentProcessor(
        config=DocumentToolsConfig(),
        enable_markdown_new=False
    )
    return processor._detect_mime_type(file_path, url)
