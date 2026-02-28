# Enhanced File Processing with markdown.new

> Complementary file processing: local PDF with complexity detection + Cloudflare markdown.new for unsupported formats.

## Executive Summary

Extend nanofolks file processing capabilities with:
1. **PDF Complexity Detection** - Analyze PDFs and use cloud extraction for complex ones
2. **Multi-format Support** - Support 20+ file formats via markdown.new API

**Duration:** 1-2 weeks  
**Risk Level:** Low (additive feature, graceful fallback)  
**Primary Benefit:** Support more file formats, better PDF processing

---

## Motivation

### Current State
- **PDF**: Local processing via `pypdf` - works well for simple documents
- **Other formats**: Not supported (DOCX, XLSX, images, etc.)

### Problems
1. **Complex PDFs fail** - Scanned docs, image-heavy PDFs, tables lose formatting
2. **Unsupported formats** - Users can't send DOCX, XLSX, images via chat
3. **No fallback** - When local processing fails, nothing else tries

### Opportunity
- Cloudflare's `markdown.new` provides free (500/day) multi-format conversion
- Can be fallback for complex PDFs
- Can be primary handler for unsupported formats

---

## Proposed Solution

### Architecture

```
File Input Flow:

┌─────────────────────────────────────────────────────────────┐
│                    File Received                            │
│              (PDF, DOCX, XLSX, Image, etc.)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Format Detection                             │
│                   (magic bytes / mime)                       │
└─────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
     ┌─────────┐         ┌───────────┐       ┌───────────┐
     │   PDF   │         │  Supported│       │ Unsupported│
     │         │         │   (txt)   │       │ (DOCX,    │
     │         │         │           │       │  XLSX,    │
     └────┬────┘         └─────┬─────┘       │  Images)  │
          │                    │              └─────┬─────┘
          ▼                    │                    │
┌─────────────────────┐        │                    │
│ PDF Complexity      │        │                    ▼
│ Analyzer            │        │           ┌──────────────────┐
│ - Page count        │        │           │ markdown.new API │
│ - Image count       │        │           │ (fallback)       │
│ - Text density     │        │           └────────┬─────────┘
└─────────┬───────────┘        │                    │
          │                    │                    │
    ┌─────┴─────┐             │                    │
    ▼           ▼             │                    │
┌────────┐  ┌──────────┐     │                    │
│ Simple │  │ Complex  │     │                    │
│   ↓    │  │    ↓     │     │                    │
│ pypdf  │  │markdown  │     │                    │
│(local) │  │ .new API │     │                    │
└────────┘  └──────────┘     │                    │
        │                    │                    │
        └────────┬────────────┴────────────────────┘
                 ▼
        ┌──────────────────┐
        │  Clean Markdown  │
        │  → Bot processes │
        └──────────────────┘
```

### Component 1: PDF Complexity Analyzer

```python
@dataclass
class PDFComplexity:
    """Complexity analysis result."""
    page_count: int
    image_count: int
    text_density: float  # chars per page
    is_complex: bool
    fallback_reason: str | None


class PDFComplexityAnalyzer:
    """Analyze PDF complexity to determine processing method."""
    
    COMPLEXITY_THRESHOLDS = {
        "max_pages": 30,
        "max_images": 10,
        "min_text_density": 200,  # chars per page
    }
    
    def analyze(self, path: Path) -> PDFComplexity:
        reader = PdfReader(str(path))
        
        # Count pages
        page_count = len(reader.pages)
        
        # Count images
        image_count = sum(
            1 for page in reader.pages
            for obj in page.get("/Resources", {}).get("/XObject", {}).values()
            if obj.get("/Subtype") == "/Image"
        )
        
        # Measure text density
        sample = "".join(
            p.extract_text() or "" 
            for p in reader.pages[:5]
        )
        text_density = len(sample) / max(page_count, 1)
        
        # Determine if complex
        is_complex = (
            page_count > self.COMPLEXITY_THRESHOLDS["max_pages"] or
            image_count > self.COMPLEXITY_THRESHOLDS["max_images"] or
            text_density < self.COMPLEXITY_THRESHOLDS["min_text_density"] or
            sample.strip() == ""  # Scanned/image-only
        )
        
        # Determine reason
        if page_count > self.COMPLEXITY_THRESHOLDS["max_pages"]:
            reason = "too_many_pages"
        elif image_count > self.COMPLEXITY_THRESHOLDS["max_images"]:
            reason = "too_many_images"
        elif sample.strip() == "":
            reason = "scanned_or_image_based"
        elif text_density < self.COMPLEXITY_THRESHOLDS["min_text_density"]:
            reason = "low_text_density"
        else:
            reason = None
            
        return PDFComplexity(
            page_count=page_count,
            image_count=image_count,
            text_density=text_density,
            is_complex=is_complex,
            fallback_reason=reason
        )
```

### Component 2: Markdown.new Integration

```python
class MarkdownNewTool(Tool):
    """Convert files to Markdown using markdown.new API."""
    
    name = "convert_file_to_markdown"
    description = """Convert various file formats to clean Markdown.
    Supports: PDF, DOCX, XLSX, ODT, ODS, Images (JPG, PNG, SVG), CSV, JSON, XML, HTML, TXT.
    Use this when you need to process documents that aren't plain text."""
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string", 
                "description": "Public URL to the file to convert"
            },
            "method": {
                "type": "string",
                "enum": ["auto", "ai", "browser"],
                "default": "auto",
                "description": "Conversion method: auto (default), ai (Workers AI), browser (headless)"
            },
            "retain_images": {
                "type": "boolean", 
                "default": False,
                "description": "Include image descriptions in output"
            }
        },
        "required": ["url"]
    }
    
    async def execute(self, url: str, method: str = "auto", retain_images: bool = False, **kwargs) -> str:
        """Convert file at URL to Markdown."""
        
        # Validate URL
        if not url.startswith(("http://", "https://")):
            return json.dumps({
                "error": "URL must start with http:// or https://",
                "url": url
            })
        
        try:
            response = await httpx.AsyncClient().post(
                "https://markdown.new/",
                json={
                    "url": url,
                    "method": method,
                    "retain_images": retain_images
                },
                timeout=30.0
            )
            
            if response.status_code == 429:
                return json.dumps({
                    "error": "Rate limit exceeded (500/day). Try again later.",
                    "url": url
                })
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                return json.dumps({
                    "success": True,
                    "title": result.get("title"),
                    "content": result.get("content"),
                    "method": result.get("method"),
                    "tokens": result.get("tokens"),
                    "url": url
                })
            else:
                return json.dumps({
                    "error": result.get("error", "Conversion failed"),
                    "url": url
                })
                
        except httpx.TimeoutException:
            return json.dumps({"error": "Conversion timed out", "url": url})
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})
```

### Component 3: Unified Document Processor

```python
class UnifiedDocumentProcessor:
    """Unified document processing with local/cloud fallback."""
    
    def __init__(self, config: DocumentToolsConfig):
        self.local = LocalDocumentProcessor(config)
        self.complexity_analyzer = PDFComplexityAnalyzer()
        self.markdown_new_enabled = True  # Configurable
    
    async def process(self, file_path: str, source: str = "upload") -> dict:
        """Process document with appropriate method."""
        
        mime_type = self._detect_mime(file_path)
        
        # Handle based on type
        if mime_type == "application/pdf":
            return await self._process_pdf(file_path)
        elif mime_type in self._supported_markdown_new():
            return await self._process_markdown_new(file_path)
        else:
            return {"error": f"Unsupported format: {mime_type}"}
    
    async def _process_pdf(self, file_path: str) -> dict:
        """Process PDF - local or cloud based on complexity."""
        
        # Analyze complexity first
        complexity = self.complexity_analyzer.analyze(Path(file_path))
        
        if not complexity.is_complex:
            # Simple PDF - use local processing
            result = self.local.process_pdfs([file_path])
            return {"method": "local", "result": result}
        else:
            # Complex PDF - use markdown.new
            if self.markdown_new_enabled:
                return await self._process_markdown_new(file_path)
            else:
                return {
                    "method": "local_limited",
                    "warning": f"Complex PDF ({complexity.fallback_reason}), local processing may be limited",
                    "result": self.local.process_pdfs([file_path])
                }
    
    async def _process_markdown_new(self, file_url: str) -> dict:
        """Process file via markdown.new API."""
        
        tool = MarkdownNewTool()
        result = await tool.execute(file_url)
        return {"method": "markdown.new", "result": result}
    
    def _supported_markdown_new(self) -> set:
        """File types supported by markdown.new."""
        return {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
            "application/vnd.oasis.opendocument.text",  # ODT
            "application/vnd.oasis.opendocument.spreadsheet",  # ODS
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
```

---

## Implementation Plan

### Phase 1: PDF Complexity Analyzer (3 days)
- [ ] Create `documents/complexity_analyzer.py`
- [ ] Detect page count, image count, text density
- [ ] Classify as simple vs complex
- [ ] Integrate into `DocumentProcessor`

### Phase 2: Markdown.new Tool (3 days)
- [ ] Create `agent/tools/markdown_convert.py`
- [ ] Implement `MarkdownNewTool`
- [ ] Add to AgentLoop tools
- [ ] Test with various formats

### Phase 3: Unified Processor (2 days)
- [ ] Create `documents/unified_processor.py`
- [ ] Route based on format and complexity
- [ ] Add fallback chain
- [ ] Config options

### Phase 4: Integration (2 days)
- [ ] Handle file uploads from all channels
- [ ] Connect to document processor
- [ ] Error handling
- [ ] Testing

---

## Configuration

```yaml
documents:
  # Local PDF processing
  auto_parse_pdf: true
  max_pages: 30
  max_chars: 200000
  
  # Complexity detection
  complexity_detection: true
  complexity_thresholds:
    max_pages: 30
    max_images: 10
    min_text_density: 200
  
  # Markdown.new integration
  use_markdown_new: true
  markdown_new_fallback: true
  markdown_new_rate_limit: 500  # per day
```

---

## Rate Limiting & Costs

| Aspect | Details |
|--------|---------|
| **Rate limit** | 500 requests/day per IP |
| **Cost** | Free (with rate limit) |
| **File size** | Max 10 MB |
| **Timeout** | 30 seconds |

### Fallback Strategy

```python
async def process_with_fallback(file_path: str) -> dict:
    """Try local first, then markdown.new."""
    
    # Try local
    try:
        return await local_process(file_path)
    except Exception as e:
        logger.warning(f"Local processing failed: {e}")
    
    # Check rate limit
    if not within_rate_limit():
        return {"error": "Rate limited, try later"}
    
    # Try markdown.new
    try:
        return await markdown_new_process(file_path)
    except Exception as e:
        return {"error": f"All methods failed: {e}"}
```

---

## Security Considerations

1. **URL validation** - Only allow http/https, block local paths
2. **File size limits** - Max 10MB (markdown.new limit)
3. **Rate limiting** - Track usage, graceful degradation
4. **Content scanning** - Still scan converted content for injections
5. **Privacy** - Note: files processed on Cloudflare edge (not 100% private)

---

## Testing Plan

| Format | Test Case | Expected |
|--------|-----------|----------|
| PDF (simple) | 5-page text document | Local processing |
| PDF (complex) | 50-page with images | Markdown.new |
| PDF (scanned) | Image-only scan | Markdown.new |
| DOCX | Word document | Markdown.new |
| XLSX | Excel spreadsheet | Markdown.new |
| Image | PNG screenshot | Markdown.new |
| CSV | CSV data | Markdown.new |

---

## Backward Compatibility

- **Default: Local first** - Existing PDF behavior unchanged
- **Opt-in** - Markdown.new disabled by default for PDFs
- **Graceful** - Falls back to local if API fails
- **Config toggle** - Users can enable/disable per format

---

## Success Metrics

- [ ] Support 20+ file formats
- [ ] Complex PDFs handled correctly
- [ ] Rate limiting works (429 responses)
- [ ] No regression in existing PDF processing
- [ ] Clear error messages for unsupported formats
