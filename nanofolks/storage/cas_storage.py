import hashlib
import json
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from loguru import logger
import fcntl


@dataclass
class CASResult:
    """Result of a CAS operation."""
    success: bool
    current_version: str
    new_version: Optional[str] = None
    error: Optional[str] = None


class CASFileStorage:
    """
    Compare-And-Set file storage for conflict-free concurrent writes.
    
    Uses ETags (content hashes) for versioning:
    - Read returns (data, etag)
    - Write only succeeds if etag matches current
    - Automatic retry on conflict
    """
    
    def __init__(self, base_path: Path, max_retries: int = 10):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        
    def _compute_etag(self, content: str) -> str:
        """Compute ETag (hash) for content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _get_path(self, key: str) -> Path:
        """Get file path for a key."""
        safe_key = key.replace(":", "_").replace("/", "_")
        return self.base_path / f"{safe_key}.jsonl"
    
    def _get_etag_path(self, key: str) -> Path:
        """Get ETag file path."""
        return self.base_path / f"{key.replace(':', '_')}.etag"
    
    def read(self, key: str) -> tuple[Optional[list], Optional[str]]:
        """
        Read data and its ETag.
        
        Returns:
            (data, etag) or (None, None) if not exists
        """
        path = self._get_path(key)
        
        if not path.exists():
            return None, None
            
        try:
            with open(path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                content = f.read()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            current_etag = self._compute_etag(content)
            
            data = []
            for line in content.strip().split('\n'):
                if line:
                    data.append(json.loads(line))
            
            return data, current_etag
            
        except Exception as e:
            logger.error(f"Error reading {key}: {e}")
            return None, None
    
    def write_cas(
        self, 
        key: str, 
        data: list, 
        expected_etag: Optional[str],
        retry_fn: Optional[Callable] = None
    ) -> CASResult:
        """
        Write data only if current ETag matches expected.
        
        Args:
            key: Storage key
            data: Data to write (list of dicts, serialized as JSONL)
            expected_etag: Expected current ETag (None for new files)
            retry_fn: Optional function to call on conflict for merge
            
        Returns:
            CASResult with success status
        """
        path = self._get_path(key)
        
        for attempt in range(self.max_retries):
            current_etag = None
            try:
                _, current_etag = self.read(key)
                
                if current_etag != expected_etag:
                    if retry_fn:
                        current_data, _ = self.read(key)
                        data = retry_fn(current_data, data)
                        _, expected_etag = self.read(key)
                        continue
                    else:
                        return CASResult(
                            success=False,
                            current_version=current_etag or "new",
                            error=f"ETag mismatch: expected {expected_etag}, got {current_etag}"
                        )
                
                lines = [json.dumps(item, default=str) for item in data]
                content = '\n'.join(lines) + '\n'
                new_etag = self._compute_etag(content)
                
                temp_path = path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(content)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                temp_path.rename(path)
                
                logger.debug(f"CAS write succeeded for {key} (attempt {attempt + 1})")
                return CASResult(
                    success=True,
                    current_version=new_etag,
                    new_version=new_etag
                )
                
            except Exception as e:
                logger.warning(f"CAS write attempt {attempt + 1} failed for {key}: {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(0.01 * (2 ** attempt))
                else:
                    return CASResult(
                        success=False,
                        current_version=current_etag or "unknown",
                        error=str(e)
                    )
        
        return CASResult(
            success=False,
            current_version="unknown",
            error="Max retries exceeded"
        )
    
    def write_with_retry(
        self, 
        key: str, 
        data: list,
        merge_fn: Optional[Callable[[list, list], list]] = None
    ) -> CASResult:
        """
        Write with automatic retry on conflict using merge function.
        
        Args:
            key: Storage key
            data: Data to write
            merge_fn: Function to merge current and new data on conflict
                     Signature: merge_fn(current_data, new_data) -> merged_data
        """
        _, current_etag = self.read(key)
        
        if merge_fn:
            return self.write_cas(key, data, current_etag, retry_fn=merge_fn)
        else:
            return self.write_cas(key, data, current_etag)


class SessionCASStorage(CASFileStorage):
    """CAS storage specialized for session management."""
    
    def merge_sessions(self, current: list, new: list) -> list:
        """
        Merge two session arrays, keeping unique messages by ID.
        
        This is called on CAS conflict to merge concurrent writes.
        """
        seen_ids = set()
        merged = []
        
        for item in current:
            msg_id = item.get('id') or item.get('_id') or hash(json.dumps(item, sort_keys=True))
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                merged.append(item)
        
        for item in new:
            msg_id = item.get('id') or item.get('_id') or hash(json.dumps(item, sort_keys=True))
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                merged.append(item)
        
        merged.sort(key=lambda x: x.get('timestamp', 0))
        
        return merged
    
    def save_session(self, session_key: str, messages: list) -> CASResult:
        """Save session with automatic conflict resolution."""
        return self.write_with_retry(
            session_key, 
            messages, 
            merge_fn=self.merge_sessions
        )
