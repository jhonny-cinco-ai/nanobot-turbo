"""Lightweight HTTP server for the dashboard using aiohttp if available, else built-in HTTP server.

Provides REST API and WebSocket support for real-time metrics updates.
"""

import asyncio
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DashboardHTTPServer:
    """Lightweight HTTP server for the dashboard.

    Attempts to use aiohttp if available, falls back to built-in solution.
    Uses secure defaults: prefers Tailscale IP and random port.
    """

    def __init__(self, dashboard_service, host: str | None = None, port: int | None = None):
        """Initialize HTTP server.

        Args:
            dashboard_service: DashboardService instance
            host: Host to bind to. If None, auto-detects best IP (Tailscale > LAN > localhost)
            port: Port to listen on. If None, finds a free random port.
        """
        self.dashboard_service = dashboard_service

        # Auto-detect secure bind address if not specified
        if host is None or port is None:
            from nanofolks.utils.network import get_secure_bind_address

            bind_addr = get_secure_bind_address("dashboard")
            self.host = host or bind_addr.host
            self.port = port or bind_addr.port

            logger.info(
                f"Auto-configured dashboard bind address: {self.host}:{self.port} "
                f"(tailscale={bind_addr.is_tailscale}, localhost={bind_addr.is_localhost})"
            )
        else:
            self.host = host
            self.port = port

        self._server: Optional[Any] = None
        self._app: Optional[Any] = None
        self._use_aiohttp = False

        # Try to import aiohttp
        try:
            import aiohttp.web
            self._use_aiohttp = True
            self.aiohttp = aiohttp
            logger.info("Using aiohttp for dashboard server")
        except ImportError:
            logger.warning("aiohttp not available, using fallback HTTP server")

    async def start(self) -> None:
        """Start the HTTP server."""
        if self._use_aiohttp:
            await self._start_aiohttp_server()
        else:
            await self._start_fallback_server()

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._use_aiohttp and self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("Dashboard HTTP server stopped")

    async def _start_aiohttp_server(self) -> None:
        """Start using aiohttp."""
        from aiohttp import web

        app = web.Application()

        # Routes
        app.router.add_get('/', self._handle_root)
        app.router.add_get('/api/health', self._handle_health)
        app.router.add_get('/api/bot/{bot_name}', self._handle_bot)
        app.router.add_get('/api/metrics', self._handle_metrics)
        app.router.add_get('/ws/metrics', self._handle_websocket)

        # Static files (embedded CSS/JS)
        app.router.add_get('/api/static/{filename}', self._handle_static)

        # Start server
        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"Dashboard server started at http://{self.host}:{self.port}")

    async def _start_fallback_server(self) -> None:
        """Start using Python's built-in HTTP server with asyncio."""
        import http.server
        import socketserver

        class DashboardHandler(http.server.BaseHTTPRequestHandler):
            dashboard = self.dashboard_service

            def do_GET(self):
                """Handle GET requests."""
                path = self.path.split('?')[0]

                if path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(self.dashboard.get_html_dashboard().encode())

                elif path == '/api/health':
                    health = self.dashboard.get_current_health()
                    self.send_json_response(health)

                elif path.startswith('/api/bot/'):
                    bot_name = path.split('/')[-1]
                    history = self.dashboard.get_bot_history(bot_name)
                    self.send_json_response(history)

                elif path == '/api/metrics':
                    metrics = self.dashboard.get_metrics_history()
                    self.send_json_response(metrics)

                else:
                    self.send_response(404)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Not Found')

            def send_json_response(self, data):
                """Send JSON response."""
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def log_message(self, format, *args):
                """Override to use our logger."""
                logger.debug(format % args)

        # Create server
        with socketserver.TCPServer((self.host, self.port), DashboardHandler) as httpd:
            self._server = httpd
            logger.info(f"Fallback dashboard server started at http://{self.host}:{self.port}")

            # Run in background
            asyncio.get_event_loop()

            # Handle server in a separate task
            async def serve():
                while self._server:
                    self._server.handle_request()
                    await asyncio.sleep(0.1)

            asyncio.create_task(serve())

    async def _handle_root(self, request):
        """Handle root page request."""
        return self.aiohttp.web.Response(
            text=self.dashboard_service.get_html_dashboard(),
            content_type='text/html; charset=utf-8'
        )

    async def _handle_health(self, request):
        """Handle /api/health request."""
        health = self.dashboard_service.get_current_health()
        return self.aiohttp.web.json_response(health)

    async def _handle_bot(self, request):
        """Handle /api/bot/{bot_name} request."""
        bot_name = request.match_info['bot_name']
        history = self.dashboard_service.get_bot_history(bot_name)
        return self.aiohttp.web.json_response(history)

    async def _handle_metrics(self, request):
        """Handle /api/metrics request."""
        metrics = self.dashboard_service.get_metrics_history()
        return self.aiohttp.web.json_response(metrics)

    async def _handle_websocket(self, request):
        """Handle WebSocket connection for real-time metrics."""
        ws = self.aiohttp.web.WebSocketResponse()
        await ws.prepare(request)

        # Create queue for this client
        queue: asyncio.Queue = asyncio.Queue()
        self.dashboard_service.register_client(queue)

        try:
            # Send initial health data
            health = self.dashboard_service.get_current_health()
            await ws.send_json(health)

            # Listen for updates
            while not ws.is_closed():
                try:
                    # Wait for metrics with timeout
                    metrics = await asyncio.wait_for(queue.get(), timeout=30)
                    await ws.send_json(metrics)
                except asyncio.TimeoutError:
                    # Send keepalive
                    await ws.send_json({"type": "ping"})
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.dashboard_service.unregister_client(queue)
            await ws.close()

        return ws

    async def _handle_static(self, request):
        """Handle static file requests."""
        filename = request.match_info['filename']

        # Only allow safe filenames
        if '..' in filename or filename.startswith('/'):
            return self.aiohttp.web.Response(status=403)

        # Return 404 for unknown static files (we embed everything in HTML)
        return self.aiohttp.web.Response(status=404)
