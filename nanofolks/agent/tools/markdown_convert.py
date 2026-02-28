"""File to Markdown conversion using markdown.new API."""

import json
from typing import Any

import httpx

from nanofolks.agent.tools.base import Tool


class MarkdownNewTool(Tool):
    """
    Convert various file formats to clean Markdown using Cloudflare's markdown.new API.
    
    Supports: PDF, DOCX, XLSX, ODT, ODS, Images (JPG, PNG, SVG), CSV, JSON, XML, HTML, TXT.
    
    API: https://markdown.new
    Rate limit: 500 requests/day per IP (free)
    """
    
    name = "convert_file_to_markdown"
    description = """Convert various file formats to clean Markdown.
    Supports: PDF, DOCX, XLSX, ODT, ODS, Images (JPG, PNG, SVG), CSV, JSON, XML, HTML, TXT.
    Use this when you need to process documents that aren't plain text.
    Returns clean Markdown optimized for LLM context."""
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
                "description": "Conversion method: auto (default, fastest), ai (Workers AI), browser (headless for JS-heavy)"
            },
            "retain_images": {
                "type": "boolean", 
                "default": False,
                "description": "Include AI-generated image descriptions in output"
            },
            "format": {
                "type": "string",
                "enum": ["text", "json"],
                "default": "json",
                "description": "Response format: text (plain) or json (with metadata)"
            }
        },
        "required": ["url"]
    }
    
    BASE_URL = "https://markdown.new"
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
    
    async def execute(
        self,
        url: str,
        method: str = "auto",
        retain_images: bool = False,
        format: str = "json",
        **kwargs: Any
    ) -> str:
        """
        Convert file at URL to Markdown.
        
        Args:
            url: Public URL to the file
            method: Conversion method (auto, ai, browser)
            retain_images: Include image descriptions
            format: Response format (text or json)
            
        Returns:
            JSON string with result or error
        """
        # Validate URL
        if not url:
            return json.dumps({
                "error": "URL is required",
                "url": url
            })
        
        if not url.startswith(("http://", "https://")):
            return json.dumps({
                "error": "URL must start with http:// or https://",
                "url": url
            })
        
        try:
            result = await self._convert(
                url=url,
                method=method,
                retain_images=retain_images,
                format=format
            )
            return json.dumps(result)
            
        except httpx.TimeoutException:
            return json.dumps({
                "error": "Conversion timed out",
                "url": url,
                "timeout": self.timeout
            })
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return json.dumps({
                    "error": "Rate limit exceeded (500/day). Try again later.",
                    "url": url,
                    "retry_after": e.response.headers.get("retry-after")
                })
            return json.dumps({
                "error": f"HTTP error: {e.response.status_code}",
                "url": url
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url
            })
    
    async def _convert(
        self,
        url: str,
        method: str,
        retain_images: bool,
        format: str
    ) -> dict[str, Any]:
        """Make the API request with retries."""
        
        client = httpx.AsyncClient(timeout=self.timeout)
        
        try:
            # Build request based on desired format
            if format == "text":
                # GET request returns plain text
                response = await client.get(
                    f"{self.BASE_URL}/{url}",
                    params={"method": method} if method != "auto" else None
                )
                response.raise_for_status()
                
                return {
                    "success": True,
                    "content": response.text,
                    "url": url,
                    "method": method
                }
            else:
                # POST returns JSON with metadata
                response = await client.post(
                    self.BASE_URL,
                    json={
                        "url": url,
                        "method": method,
                        "retain_images": retain_images
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    return {
                        "success": True,
                        "title": result.get("title"),
                        "content": result.get("content"),
                        "method": result.get("method"),
                        "tokens": result.get("tokens"),
                        "duration_ms": result.get("duration"),
                        "url": url
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Conversion failed"),
                        "url": url
                    }
                    
        finally:
            await client.aclose()


# Convenience function for direct conversion
async def convert_file_to_markdown(
    url: str,
    method: str = "auto",
    retain_images: bool = False
) -> dict[str, Any]:
    """
    Convert a file to Markdown using markdown.new API.
    
    Args:
        url: Public URL to the file
        method: Conversion method (auto, ai, browser)
        retain_images: Include image descriptions
        
    Returns:
        Dict with success status and content/metadata
    """
    tool = MarkdownNewTool()
    result = await tool.execute(
        url=url,
        method=method,
        retain_images=retain_images,
        format="json"
    )
    return json.loads(result)
