"""Network utilities for secure binding and Tailscale detection."""

import random
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional

from loguru import logger


TAILSCALE_IP_PREFIX = "100."
COMMON_PORT_RANGE = (8000, 9000)
DEFAULT_PORTS = {
    "dashboard": 9090,
    "bridge": 3001,
}


@dataclass
class BindAddress:
    """Represents a secure bind address."""
    host: str
    port: int
    is_tailscale: bool = False
    is_localhost: bool = False


def get_all_ips() -> list[str]:
    """Get all non-loopback IP addresses on this machine."""
    ips = []
    try:
        # Get all network interfaces
        result = subprocess.run(
            ["ip", "-4", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in result.stdout.split("\n"):
            if "inet " in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    ip = parts[1].split("/")[0]
                    if ip != "127.0.0.1":
                        ips.append(ip)
    except Exception:
        # Fallback: try socket method
        pass
    
    # Also try socket method
    try:
        hostname = socket.gethostname()
        # Get all addresses (IPv4)
        for addr_info in socket.getaddrinfo(hostname, None):
            ip = addr_info[4][0]
            if ":" not in ip and ip != "127.0.0.1" and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    
    return ips


def get_tailscale_ip() -> Optional[str]:
    """Get Tailscale IP if available.
    
    Returns:
        Tailscale IP (100.x.x.x) if found, None otherwise.
    """
    # Try tailscale command first (most reliable)
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ip = result.stdout.strip()
            if ip.startswith(TAILSCALE_IP_PREFIX):
                logger.info(f"Found Tailscale IP: {ip}")
                return ip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback: scan local IPs for Tailscale prefix
    for ip in get_all_ips():
        if ip.startswith(TAILSCALE_IP_PREFIX):
            logger.info(f"Found Tailscale IP (scanned): {ip}")
            return ip
    
    return None


def get_best_ip() -> str:
    """Get the best IP address to bind to.
    
    Priority:
    1. Tailscale IP (100.x.x.x) - encrypted, private network
    2. Private LAN IP (192.168.x.x, 10.x.x.x) - local network
    3. localhost (127.0.0.1) - single user, no network access
    
    Returns:
        Best IP address to use for binding.
    """
    ips = get_all_ips()
    
    # Priority 1: Tailscale
    tailscale_ip = get_tailscale_ip()
    if tailscale_ip:
        return tailscale_ip
    
    # Priority 2: Private LAN (192.168.x.x or 10.x.x.x)
    for ip in ips:
        if ip.startswith("192.168.") or ip.startswith("10."):
            return ip
    
    # Priority 3: Any other non-loopback
    if ips:
        return ips[0]
    
    # Fallback: localhost
    return "127.0.0.1"


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is available.
    
    Args:
        port: Port number to check.
        host: Host to check on.
    
    Returns:
        True if port is available, False otherwise.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def find_free_port(
    start: int = COMMON_PORT_RANGE[0],
    end: int = COMMON_PORT_RANGE[1],
    host: str = "0.0.0.0"
) -> int:
    """Find a free port in the given range.
    
    Args:
        start: Start of port range (inclusive).
        end: End of port range (exclusive).
        host: Host to check on.
    
    Returns:
        Available port number.
    """
    # Try random ports first (security through obscurity)
    attempts = min(20, end - start)
    for _ in range(attempts):
        port = random.randint(start, end - 1)
        if is_port_available(port, host):
            return port
    
    # Fallback: scan sequentially
    for port in range(start, end):
        if is_port_available(port, host):
            return port
    
    # Last resort: return default
    logger.warning(f"Could not find free port in range, using default")
    return start


def get_secure_bind_address(
    service: str = "default",
    prefer_tailscale: bool = True
) -> BindAddress:
    """Get a secure bind address for a service.
    
    This function determines the best IP and port combination
    for binding a service securely.
    
    Args:
        service: Service name for default port fallback.
        prefer_tailscale: If True, prefer Tailscale IP.
    
    Returns:
        BindAddress with host, port, and metadata.
    """
    # Determine host
    host = "127.0.0.1"
    is_tailscale = False
    is_localhost = True
    
    if prefer_tailscale:
        tailscale_ip = get_tailscale_ip()
        if tailscale_ip:
            host = tailscale_ip
            is_tailscale = True
            is_localhost = False
            logger.info(f"Using Tailscale IP: {host}")
        else:
            # Fallback to best private IP
            best_ip = get_best_ip()
            if best_ip != "127.0.0.1":
                host = best_ip
                is_localhost = False
                logger.info(f"Using private IP: {host}")
    
    # Determine port
    default_port = DEFAULT_PORTS.get(service, 8080)
    
    # Try to find a free random port first
    port = find_free_port()
    
    # If random port is far from default, good - but also try default
    # to ensure we get something usable
    if not is_port_available(port, host):
        port = default_port
        # If default also taken, find any free port
        if not is_port_available(port, host):
            port = find_free_port()
    
    return BindAddress(
        host=host,
        port=port,
        is_tailscale=is_tailscale,
        is_localhost=is_localhost
    )


def format_bind_url(addr: BindAddress, use_https: bool = False) -> str:
    """Format a bind address as a URL.
    
    Args:
        addr: BindAddress to format.
        use_https: Whether to use HTTPS.
    
    Returns:
        Formatted URL string.
    """
    scheme = "https" if use_https else "ws" if addr.port in (3001, 3002) else "http"
    return f"{scheme}://{addr.host}:{addr.port}"
