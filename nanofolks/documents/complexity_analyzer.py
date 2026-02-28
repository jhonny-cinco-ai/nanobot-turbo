"""PDF complexity analysis to determine processing method."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


@dataclass
class PDFComplexity:
    """Complexity analysis result for a PDF."""
    page_count: int
    image_count: int
    text_density: float  # average characters per page
    is_complex: bool
    fallback_reason: str | None
    
    def to_dict(self) -> dict:
        return {
            "page_count": self.page_count,
            "image_count": self.image_count,
            "text_density": self.text_density,
            "is_complex": self.is_complex,
            "fallback_reason": self.fallback_reason,
        }


class PDFComplexityAnalyzer:
    """
    Analyze PDF complexity to determine if local or cloud processing is better.
    
    Complexity is determined by:
    - Page count: > 30 pages = complex
    - Image count: > 10 images = complex  
    - Text density: < 200 chars/page = likely scanned/image-based
    - Empty text: no extractable text = scanned/image-only PDF
    """
    
    DEFAULT_THRESHOLDS = {
        "max_pages": 30,
        "max_images": 10,
        "min_text_density": 200,
    }
    
    def __init__(self, thresholds: dict | None = None):
        """
        Initialize with custom thresholds.
        
        Args:
            thresholds: Optional dict with max_pages, max_images, min_text_density
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
    
    def analyze(self, path: str | Path) -> PDFComplexity | None:
        """
        Analyze a PDF file for complexity.
        
        Args:
            path: Path to PDF file
            
        Returns:
            PDFComplexity with analysis results, or None if file can't be read
        """
        if PdfReader is None:
            logger.warning("pypdf not installed, cannot analyze PDF complexity")
            return None
            
        path = Path(path)
        
        if not path.exists():
            logger.warning(f"PDF file not found: {path}")
            return None
            
        try:
            reader = PdfReader(str(path))
        except Exception as e:
            logger.warning(f"Failed to read PDF {path}: {e}")
            return None
        
        # Get page count
        page_count = len(reader.pages)
        
        # Count images across all pages
        image_count = self._count_images(reader)
        
        # Measure text density from sample pages
        text_density, sample_text = self._measure_text_density(reader)
        
        # Determine complexity
        is_complex, fallback_reason = self._determine_complexity(
            page_count=page_count,
            image_count=image_count,
            text_density=text_density,
            has_text=bool(sample_text.strip())
        )
        
        result = PDFComplexity(
            page_count=page_count,
            image_count=image_count,
            text_density=text_density,
            is_complex=is_complex,
            fallback_reason=fallback_reason
        )
        
        logger.debug(
            f"PDF complexity analysis: {path.name} - "
            f"pages={page_count}, images={image_count}, "
            f"density={text_density:.0f}, complex={is_complex}"
        )
        
        return result
    
    def _count_images(self, reader: PdfReader) -> int:
        """Count total images in PDF."""
        image_count = 0
        
        try:
            for page in reader.pages:
                if "/Resources" not in page:
                    continue
                    
                resources = page["/Resources"]
                
                if "/XObject" not in resources:
                    continue
                    
                xobjects = resources["/XObject"].get_object()
                
                for obj in xobjects.values():
                    if obj.get("/Subtype") == "/Image":
                        image_count += 1
                        
        except Exception as e:
            logger.debug(f"Error counting images: {e}")
        
        return image_count
    
    def _measure_text_density(self, reader: PdfReader) -> tuple[float, str]:
        """
        Measure text density (chars per page) from sample pages.
        
        Returns:
            Tuple of (text_density, sample_text)
        """
        # Sample first 10 pages or all if fewer
        sample_pages = min(10, len(reader.pages))
        sample_text = ""
        
        try:
            for page in reader.pages[:sample_pages]:
                page_text = page.extract_text() or ""
                sample_text += page_text
        except Exception as e:
            logger.debug(f"Error extracting text: {e}")
        
        # Calculate density
        if sample_pages > 0:
            text_density = len(sample_text) / sample_pages
        else:
            text_density = 0.0
            
        return text_density, sample_text
    
    def _determine_complexity(
        self,
        page_count: int,
        image_count: int,
        text_density: float,
        has_text: bool
    ) -> tuple[bool, str | None]:
        """
        Determine if PDF is complex based on thresholds.
        
        Returns:
            Tuple of (is_complex, fallback_reason)
        """
        # Check page count
        if page_count > self.thresholds["max_pages"]:
            return True, "too_many_pages"
        
        # Check image count
        if image_count > self.thresholds["max_images"]:
            return True, "too_many_images"
        
        # Check for scanned/image-only PDF
        if not has_text:
            return True, "scanned_or_image_based"
        
        # Check text density
        if text_density < self.thresholds["min_text_density"]:
            return True, "low_text_density"
        
        # Not complex
        return False, None
    
    def should_use_cloud(self, path: str | Path) -> tuple[bool, str | None]:
        """
        Quick check if cloud processing should be used.
        
        Returns:
            Tuple of (should_use_cloud, reason)
        """
        result = self.analyze(path)
        
        if result is None:
            # Can't analyze, assume local
            return False, None
            
        return result.is_complex, result.fallback_reason


def analyze_pdf_complexity(path: str | Path, thresholds: dict | None = None) -> PDFComplexity | None:
    """
    Convenience function to analyze PDF complexity.
    
    Args:
        path: Path to PDF file
        thresholds: Optional custom thresholds
        
    Returns:
        PDFComplexity result
    """
    analyzer = PDFComplexityAnalyzer(thresholds)
    return analyzer.analyze(path)


def should_use_markdown_new(path: str | Path, thresholds: dict | None = None) -> tuple[bool, str | None]:
    """
    Convenience function to check if markdown.new should be used.
    
    Args:
        path: Path to PDF file
        thresholds: Optional custom thresholds
        
    Returns:
        Tuple of (should_use, reason)
    """
    analyzer = PDFComplexityAnalyzer(thresholds)
    return analyzer.should_use_cloud(path)
