"""Auto-calibration system for improving routing decisions over time."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import RoutingPattern, RoutingTier


class CalibrationManager:
    """
    Manages auto-calibration of routing patterns and thresholds.
    
    Runs periodically to:
    1. Analyze classification accuracy
    2. Generate new patterns from successful LLM classifications
    3. Update confidence thresholds
    4. Evict low-success patterns
    """
    
    def __init__(
        self,
        patterns_file: Path,
        analytics_file: Optional[Path] = None,
        config: Optional[dict] = None,
    ):
        self.patterns_file = patterns_file
        self.analytics_file = analytics_file or patterns_file.parent / "routing_stats.json"
        self.config = config or {}
        
        # Default configuration
        self.interval = self.config.get("interval", "24h")
        self.min_classifications = self.config.get("min_classifications", 50)
        self.max_patterns = self.config.get("max_patterns", 100)
        self.backup_before = self.config.get("backup_before_calibration", True)
        
        self._classifications: list[dict] = []
        self._last_calibration: Optional[datetime] = None
        self._load_analytics()
    
    def _load_analytics(self) -> None:
        """Load analytics data from file."""
        if self.analytics_file.exists():
            try:
                data = json.loads(self.analytics_file.read_text())
                self._classifications = data.get("classifications", [])
                last_str = data.get("last_calibration")
                if last_str:
                    self._last_calibration = datetime.fromisoformat(last_str)
            except Exception:
                self._classifications = []
                self._last_calibration = None
    
    def record_classification(self, record: dict) -> None:
        """
        Record a classification for later analysis.
        
        Args:
            record: Dict with keys like:
                - content_preview
                - client_tier
                - client_confidence
                - llm_tier (optional)
                - llm_confidence (optional)
                - final_tier
                - timestamp
        """
        record["timestamp"] = datetime.now().isoformat()
        self._classifications.append(record)
        
        # Keep only recent classifications (last 1000)
        if len(self._classifications) > 1000:
            self._classifications = self._classifications[-1000:]
    
    def should_calibrate(self) -> bool:
        """Check if calibration should run."""
        if not self._classifications:
            return False
        
        # Check time-based interval
        if self._last_calibration:
            interval_hours = self._parse_interval(self.interval)
            time_since = datetime.now() - self._last_calibration
            if time_since < timedelta(hours=interval_hours):
                # Check count-based threshold
                classifications_since = len([
                    c for c in self._classifications
                    if datetime.fromisoformat(c["timestamp"]) > self._last_calibration
                ])
                if classifications_since < self.min_classifications:
                    return False
        
        return True
    
    def calibrate(self) -> dict:
        """
        Run calibration and return results.
        
        Returns:
            Dict with calibration results
        """
        if self.backup_before and self.patterns_file.exists():
            self._backup_patterns()
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "classifications_analyzed": len(self._classifications),
            "patterns_added": 0,
            "patterns_removed": 0,
            "threshold_adjustments": {},
        }
        
        # Analyze accuracy
        accuracy_report = self._analyze_accuracy()
        
        # Generate new patterns from mismatches
        new_patterns = self._generate_patterns(accuracy_report["mismatches"])
        
        # Load existing patterns
        existing_patterns = self._load_existing_patterns()
        
        # Add new patterns
        for pattern in new_patterns:
            if len(existing_patterns) < self.max_patterns:
                existing_patterns.append(pattern)
                results["patterns_added"] += 1
        
        # Evict low-success patterns
        before_count = len(existing_patterns)
        existing_patterns = self._evict_patterns(existing_patterns)
        results["patterns_removed"] = before_count - len(existing_patterns)
        
        # Save updated patterns
        self._save_patterns(existing_patterns)
        
        # Update analytics
        self._last_calibration = datetime.now()
        self._save_analytics()
        
        results["total_patterns"] = len(existing_patterns)
        return results
    
    def _analyze_accuracy(self) -> dict:
        """Analyze classification accuracy."""
        total = len(self._classifications)
        matches = 0
        mismatches = []
        
        for record in self._classifications:
            client_tier = record.get("client_tier")
            llm_tier = record.get("llm_tier")
            
            if llm_tier and client_tier:
                if client_tier == llm_tier:
                    matches += 1
                else:
                    mismatches.append(record)
        
        accuracy = matches / total if total > 0 else 0.0
        
        return {
            "total": total,
            "matches": matches,
            "accuracy": accuracy,
            "mismatches": mismatches,
        }
    
    def _generate_patterns(self, mismatches: list[dict]) -> list[RoutingPattern]:
        """Generate new patterns from mismatched classifications."""
        patterns = []
        
        # Group mismatches by correct tier
        by_tier: dict[str, list[dict]] = {}
        for m in mismatches:
            tier = m.get("llm_tier", "medium")
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(m)
        
        # Analyze each tier group for common patterns
        for tier, records in by_tier.items():
            if len(records) < 3:  # Need at least 3 examples
                continue
            
            # Extract common words/phrases
            content_samples = [r.get("content_preview", "") for r in records]
            common_patterns = self._extract_patterns(content_samples)
            
            for pattern_text in common_patterns[:3]:  # Top 3 patterns per tier
                pattern = RoutingPattern(
                    regex=pattern_text,
                    tier=RoutingTier(tier),
                    confidence=0.8,
                    examples=content_samples[:3],
                    added_at=datetime.now().isoformat(),
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_patterns(self, contents: list[str]) -> list[str]:
        """Extract common patterns from content samples."""
        # Simple pattern extraction - look for common words/phrases
        words_by_content = []
        for content in contents:
            words = set(re.findall(r'\b\w+\b', content.lower()))
            words_by_content.append(words)
        
        # Find words common to multiple contents
        if not words_by_content:
            return []
        
        common_words = set.intersection(*words_by_content[:min(5, len(words_by_content))])
        
        # Filter for meaningful words (length > 3)
        meaningful = [w for w in common_words if len(w) > 3]
        
        # Create regex patterns
        patterns = []
        for word in meaningful[:10]:  # Top 10 words
            patterns.append(rf"\b{re.escape(word)}\b")
        
        return patterns
    
    def _evict_patterns(self, patterns: list[RoutingPattern]) -> list[RoutingPattern]:
        """Remove low-success patterns."""
        # Keep patterns with good success rates or recent additions
        threshold = 0.3  # Minimum 30% success rate
        
        filtered = []
        for p in patterns:
            # Keep if high success or recently added
            if p.success_rate >= threshold:
                filtered.append(p)
            else:
                # Check if recently added (< 7 days)
                try:
                    added = datetime.fromisoformat(p.added_at)
                    if datetime.now() - added < timedelta(days=7):
                        filtered.append(p)
                except:
                    pass
        
        return filtered
    
    def _load_existing_patterns(self) -> list[RoutingPattern]:
        """Load existing patterns from file."""
        if not self.patterns_file.exists():
            return []
        
        try:
            data = json.loads(self.patterns_file.read_text())
            return [RoutingPattern.from_dict(p) for p in data.get("patterns", [])]
        except Exception:
            return []
    
    def _save_patterns(self, patterns: list[RoutingPattern]) -> None:
        """Save patterns to file."""
        data = {
            "patterns": [p.to_dict() for p in patterns],
            "version": "1.0",
            "last_calibration": datetime.now().isoformat(),
            "total_classifications": len(self._classifications),
        }
        
        self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
        self.patterns_file.write_text(json.dumps(data, indent=2))
    
    def _backup_patterns(self) -> None:
        """Create backup of current patterns."""
        if self.patterns_file.exists():
            backup_file = self.patterns_file.with_suffix(".backup.json")
            backup_file.write_text(self.patterns_file.read_text())
    
    def _save_analytics(self) -> None:
        """Save analytics data."""
        data = {
            "classifications": self._classifications,
            "last_calibration": self._last_calibration.isoformat() if self._last_calibration else None,
        }
        
        self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
        self.analytics_file.write_text(json.dumps(data, indent=2))
    
    def _parse_interval(self, interval: str) -> int:
        """Parse interval string to hours."""
        try:
            if interval.endswith("h"):
                return int(interval[:-1])
            elif interval.endswith("d"):
                return int(interval[:-1]) * 24
            elif interval.isdigit():
                return int(interval)
            else:
                return 24  # Default 24 hours
        except ValueError:
            return 24  # Default 24 hours on any parsing error
