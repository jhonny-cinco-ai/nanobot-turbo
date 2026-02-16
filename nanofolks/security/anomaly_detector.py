"""Anomaly detection for suspicious security activity.

This module provides anomaly detection to identify potentially
malicious activity such as:
- Unusual request rates (potential exfiltration)
- High error rates (potential abuse)
- Large response sizes (potential data theft)
- Unusual access patterns
"""

from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class Anomaly:
    """Represents a detected security anomaly."""
    severity: str  # "low", "medium", "high", "critical"
    description: str
    key_ref: str
    detected_at: str
    details: Optional[dict] = None


class AnomalyDetector:
    """Detects suspicious patterns in key usage.
    
    This class monitors audit logs and key usage patterns to identify
    potential security issues.
    
    Example:
        >>> detector = AnomalyDetector()
        >>> anomaly = detector.check_request_rate("{{openrouter_key}}", requests_per_minute=65)
        >>> if anomaly:
        ...     logger.warning(f"ALERT: {anomaly.description}")
    """
    
    def __init__(self):
        """Initialize the anomaly detector."""
        self.request_times: dict[str, list[datetime]] = defaultdict(list)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.response_sizes: dict[str, list[float]] = defaultdict(list)
        
        # Thresholds (configurable)
        self.max_requests_per_minute = 60
        self.max_requests_per_hour = 1000
        self.max_errors_per_window = 5
        self.max_response_size_mb = 10.0
        
    def _cleanup_old_entries(self, key_ref: str) -> None:
        """Remove entries older than 1 hour to prevent memory growth."""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        # Clean request times
        self.request_times[key_ref] = [
            t for t in self.request_times[key_ref]
            if t > cutoff
        ]
        
        # Clean response sizes
        self.response_sizes[key_ref] = []
    
    def record_request(self, key_ref: str) -> None:
        """Record a request for this key.
        
        Args:
            key_ref: The symbolic key reference
        """
        now = datetime.utcnow()
        self.request_times[key_ref].append(now)
        self._cleanup_old_entries(key_ref)
    
    def record_error(self, key_ref: str) -> None:
        """Record an error for this key.
        
        Args:
            key_ref: The symbolic key reference
        """
        self.error_counts[key_ref] += 1
    
    def record_response_size(self, key_ref: str, size_mb: float) -> None:
        """Record response size for this key.
        
        Args:
            key_ref: The symbolic key reference
            size_mb: Response size in megabytes
        """
        self.response_sizes[key_ref].append(size_mb)
    
    def check_request_rate(self, key_ref: str) -> Optional[Anomaly]:
        """Check for suspicious request rates.
        
        Monitors for:
        - More than max_requests_per_minute in a minute
        - More than max_requests_per_hour in an hour
        
        Args:
            key_ref: The symbolic key reference to check
            
        Returns:
            Anomaly if detected, None otherwise
        """
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        requests = self.request_times.get(key_ref, [])
        
        # Count requests in last minute
        last_minute = len([t for t in requests if t > one_minute_ago])
        
        if last_minute > self.max_requests_per_minute:
            return Anomaly(
                severity="high",
                description=f"Request rate exceeded: {last_minute} requests/min (limit: {self.max_requests_per_minute})",
                key_ref=key_ref,
                detected_at=now.isoformat() + "Z",
                details={
                    "requests_per_minute": last_minute,
                    "limit": self.max_requests_per_minute
                }
            )
        
        # Count requests in last hour
        last_hour = len([t for t in requests if t > one_hour_ago])
        
        if last_hour > self.max_requests_per_hour:
            return Anomaly(
                severity="medium",
                description=f"Hourly request limit approached: {last_hour}/{self.max_requests_per_hour}",
                key_ref=key_ref,
                detected_at=now.isoformat() + "Z",
                details={
                    "requests_per_hour": last_hour,
                    "limit": self.max_requests_per_hour
                }
            )
        
        return None
    
    def check_error_rate(self, key_ref: str) -> Optional[Anomaly]:
        """Check for high error rates.
        
        Monitors for sustained error patterns that might indicate
        abuse or credential issues.
        
        Args:
            key_ref: The symbolic key reference to check
            
        Returns:
            Anomaly if detected, None otherwise
        """
        error_count = self.error_counts.get(key_ref, 0)
        
        if error_count > self.max_errors_per_window:
            return Anomaly(
                severity="medium",
                description=f"High error rate: {error_count} errors detected",
                key_ref=key_ref,
                detected_at=datetime.utcnow().isoformat() + "Z",
                details={
                    "error_count": error_count,
                    "limit": self.max_errors_per_window
                }
            )
        
        return None
    
    def check_response_size(self, key_ref: str) -> Optional[Anomaly]:
        """Check for unusually large responses.
        
        Large responses could indicate data exfiltration attempts.
        
        Args:
            key_ref: The symbolic key reference to check
            
        Returns:
            Anomaly if detected, None otherwise
        """
        sizes = self.response_sizes.get(key_ref, [])
        
        if not sizes:
            return None
        
        avg_size = sum(sizes) / len(sizes)
        
        if avg_size > self.max_response_size_mb:
            return Anomaly(
                severity="high",
                description=f"Large response sizes detected: avg {avg_size:.1f}MB (limit: {self.max_response_size_mb}MB)",
                key_ref=key_ref,
                detected_at=datetime.utcnow().isoformat() + "Z",
                details={
                    "average_size_mb": avg_size,
                    "limit_mb": self.max_response_size_mb,
                    "sample_count": len(sizes)
                }
            )
        
        return None
    
    def check_all(self, key_ref: str) -> list[Anomaly]:
        """Run all anomaly checks for a key.
        
        Args:
            key_ref: The symbolic key reference to check
            
        Returns:
            List of detected anomalies (may be empty)
        """
        anomalies = []
        
        # Check request rate
        rate_anomaly = self.check_request_rate(key_ref)
        if rate_anomaly:
            anomalies.append(rate_anomaly)
        
        # Check error rate
        error_anomaly = self.check_error_rate(key_ref)
        if error_anomaly:
            anomalies.append(error_anomaly)
        
        # Check response size
        size_anomaly = self.check_response_size(key_ref)
        if size_anomaly:
            anomalies.append(size_anomaly)
        
        return anomalies
    
    def reset(self, key_ref: Optional[str] = None) -> None:
        """Reset counters for a key or all keys.
        
        Args:
            key_ref: Optional specific key to reset, or None to reset all
        """
        if key_ref:
            self.request_times.pop(key_ref, None)
            self.error_counts.pop(key_ref, None)
            self.response_sizes.pop(key_ref, None)
        else:
            self.request_times.clear()
            self.error_counts.clear()
            self.response_sizes.clear()


# Global detector instance
_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get the global anomaly detector instance.
    
    Returns:
        The global AnomalyDetector instance
    """
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
