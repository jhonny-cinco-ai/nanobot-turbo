"""Dashboard service for monitoring bot crew routines in real-time.

Provides:
- REST API endpoints for crew routines metrics
- WebSocket support for real-time updates
- Health visualization
- Historical metrics tracking
- Alert management

Usage:
    from nanofolks.routines.crew.dashboard import DashboardService

    dashboard = DashboardService(port=9090, manager=multi_manager)
    await dashboard.start()
    # Navigate to http://localhost:9090
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from nanofolks.metrics import get_metrics

logger = logging.getLogger(__name__)


class MetricsBuffer:
    """Circular buffer for storing historical metrics."""

    def __init__(self, max_entries: int = 1000):
        """Initialize metrics buffer.

        Args:
            max_entries: Maximum number of entries to store
        """
        self.max_entries = max_entries
        self.entries: deque = deque(maxlen=max_entries)

    def add(self, metrics: Dict[str, Any]) -> None:
        """Add metrics entry with timestamp."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            **metrics
        }
        self.entries.append(entry)

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent metrics entries."""
        return list(self.entries)[-limit:]

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all metrics entries."""
        return list(self.entries)

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()


class DashboardService:
    """Service for providing real-time dashboard metrics.

    Integrates with MultiCrewRoutinesManager to expose:
    - Team health status
    - Per-bot metrics
    - Historical trends
    - Alert timeline
    """

    def __init__(
        self,
        manager: Optional[Any] = None,
        port: int = 9090,
        host: str = "localhost",
        update_interval: float = 5.0,  # seconds
    ):
        """Initialize dashboard service.

        Args:
            manager: MultiCrewRoutinesManager instance
            port: Port to serve dashboard on
            host: Host to bind to
            update_interval: Interval for metrics collection (seconds)
        """
        self.manager = manager
        self.port = port
        self.host = host
        self.update_interval = update_interval

        self.metrics_buffer = MetricsBuffer(max_entries=1000)
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._ws_clients: List[asyncio.Queue] = []

    async def start(self) -> None:
        """Start the dashboard service."""
        if self._running:
            logger.warning("Dashboard already running")
            return

        self._running = True

        # Start metrics collection loop
        self._update_task = asyncio.create_task(self._update_metrics_loop())

        logger.info(f"Dashboard service started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the dashboard service."""
        if not self._running:
            return

        self._running = False

        # Stop metrics collection
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        logger.info("Dashboard service stopped")

    async def _update_metrics_loop(self) -> None:
        """Continuously collect and broadcast metrics."""
        while self._running:
            try:
                # Collect metrics from manager
                if self.manager:
                    metrics = await self._collect_metrics()
                    self.metrics_buffer.add(metrics)

                    # Broadcast to WebSocket clients
                    await self._broadcast_to_clients(metrics)

                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from manager."""
        try:
            health = self.manager.get_team_health()
            internal_metrics = get_metrics().snapshot()

            return {
                "timestamp": datetime.now().isoformat(),
                "team": {
                    "overall_success_rate": health.overall_success_rate,
                    "total_bots": health.total_bots,
                    "running_bots": health.running_bots,
                    "total_ticks": health.total_ticks_all_bots,
                    "failed_ticks": health.failed_ticks_all_bots,
                },
                "bots": health.bots,
                "alerts": health.alerts,
                "internal_metrics": internal_metrics,
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "team": {
                    "overall_success_rate": 0.0,
                    "total_bots": 0,
                    "running_bots": 0,
                },
                "bots": {},
                "alerts": [f"Error collecting metrics: {str(e)}"],
                "internal_metrics": {"counters": {}, "gauges": {}},
            }

    async def _broadcast_to_clients(self, metrics: Dict[str, Any]) -> None:
        """Broadcast metrics to all connected WebSocket clients."""
        dead_clients = []

        for queue in self._ws_clients:
            try:
                queue.put_nowait(metrics)
            except asyncio.QueueFull:
                dead_clients.append(queue)

        # Remove dead clients
        for queue in dead_clients:
            try:
                self._ws_clients.remove(queue)
            except ValueError:
                pass

    def register_client(self, queue: asyncio.Queue) -> None:
        """Register a WebSocket client for updates."""
        self._ws_clients.append(queue)

    def unregister_client(self, queue: asyncio.Queue) -> None:
        """Unregister a WebSocket client."""
        try:
            self._ws_clients.remove(queue)
        except ValueError:
            pass

    def get_current_health(self) -> Dict[str, Any]:
        """Get current team health snapshot."""
        if not self.manager:
            return {
                "error": "Manager not initialized",
                "timestamp": datetime.now().isoformat(),
            }

        try:
            health = self.manager.get_team_health()
            return {
                "timestamp": health.timestamp,
                "overall_success_rate": health.overall_success_rate,
                "total_bots": health.total_bots,
                "running_bots": health.running_bots,
                "total_ticks": health.total_ticks_all_bots,
                "failed_ticks": health.failed_ticks_all_bots,
                "bots": health.bots,
                "alerts": health.alerts,
            }
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_bot_history(self, bot_name: str, limit: int = 100) -> Dict[str, Any]:
        """Get crew routines history for a specific bot."""
        if not self.manager:
            return {"error": "Manager not initialized"}

        try:
            bot = self.manager.get_bot(bot_name)
            if not bot:
                return {"error": f"Bot '{bot_name}' not found"}

            history = bot.private_memory.get("crew_routines_history", [])
            return {
                "bot_name": bot_name,
                "history": history[-limit:],
                "total_entries": len(history),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_metrics_history(self, limit: int = 100) -> Dict[str, Any]:
        """Get historical metrics."""
        return {
            "entries": self.metrics_buffer.get_recent(limit),
            "total_buffered": len(self.metrics_buffer.entries),
        }

    def get_html_dashboard(self) -> str:
        """Return the HTML dashboard page."""
        return self._get_dashboard_html()

    def _get_dashboard_html(self) -> str:
        """Generate the dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>nanoFolks CrewRoutines Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1a202c 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(30, 30, 30, 0.8);
            border-radius: 10px;
            border-left: 4px solid #3b82f6;
        }

        h1 {
            font-size: 28px;
            font-weight: 600;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-dot.connected {
            background-color: #10b981;
        }

        .status-dot.disconnected {
            background-color: #ef4444;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(30, 30, 30, 0.8);
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #3b82f6;
        }

        .card.team-health {
            grid-column: 1 / -1;
        }

        .card h2 {
            font-size: 14px;
            font-weight: 600;
            color: #94a3b8;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .health-bar {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .bar {
            flex: 1;
            height: 30px;
            background: rgba(100, 100, 100, 0.2);
            border-radius: 5px;
            overflow: hidden;
            position: relative;
        }

        .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #3b82f6);
            border-radius: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            transition: width 0.3s ease;
        }

        .percentage {
            min-width: 50px;
            text-align: right;
            font-weight: 600;
        }

        .metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }

        .system-metrics {
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
            max-height: 260px;
            overflow: auto;
        }

        .metric-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            font-size: 12px;
            background: rgba(100, 100, 100, 0.08);
            padding: 8px 10px;
            border-radius: 6px;
        }

        .metric-name {
            color: #cbd5f5;
            flex: 1;
            word-break: break-all;
        }

        .metric-value {
            color: #e2e8f0;
            font-weight: 600;
        }

        .metric-empty {
            color: #94a3b8;
            font-size: 12px;
        }

        .metric {
            background: rgba(100, 100, 100, 0.1);
            padding: 12px;
            border-radius: 5px;
        }

        .metric-label {
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 5px;
        }

        .metric-value {
            font-size: 20px;
            font-weight: 600;
        }

        .bot-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }

        .bot-item {
            background: rgba(100, 100, 100, 0.1);
            padding: 15px;
            border-radius: 5px;
            border-left: 3px solid #3b82f6;
        }

        .bot-name {
            font-weight: 600;
            margin-bottom: 10px;
        }

        .bot-status {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .bot-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ef4444;
        }

        .bot-dot.running {
            background: #10b981;
        }

        .bot-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 12px;
        }

        .stat {
            background: rgba(100, 100, 100, 0.2);
            padding: 8px;
            border-radius: 3px;
        }

        .stat-label {
            color: #94a3b8;
            font-size: 11px;
        }

        .stat-value {
            font-weight: 600;
            margin-top: 3px;
        }

        .alerts {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
        }

        .alerts h3 {
            font-size: 14px;
            margin-bottom: 10px;
            color: #fca5a5;
        }

        .alert-item {
            font-size: 13px;
            color: #fecaca;
            margin-bottom: 8px;
            padding-left: 12px;
            border-left: 2px solid #fca5a5;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
        }

        .error {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
            padding: 15px;
            border-radius: 5px;
            color: #fca5a5;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 nanoFolks CrewRoutines Dashboard</h1>
            <div class="status-indicator">
                <span class="status-dot connected" id="connectionStatus"></span>
                <span id="connectionText">Connected</span>
            </div>
        </header>

        <div id="content">
            <div class="loading">Loading dashboard...</div>
        </div>
    </div>

    <script>
        let ws = null;
        const maxRetries = 5;
        let retries = 0;

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/metrics`;

            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('connectionStatus').className = 'status-dot connected';
                document.getElementById('connectionText').textContent = 'Connected';
                retries = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const metrics = JSON.parse(event.data);
                    updateDashboard(metrics);
                } catch (e) {
                    console.error('Error parsing metrics:', e);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('connectionStatus').className = 'status-dot disconnected';
                document.getElementById('connectionText').textContent = 'Disconnected';
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected, reconnecting...');
                document.getElementById('connectionStatus').className = 'status-dot disconnected';
                document.getElementById('connectionText').textContent = 'Reconnecting...';

                if (retries < maxRetries) {
                    retries++;
                    setTimeout(connectWebSocket, 3000);
                }
            };
        }

        function updateDashboard(metrics) {
            const team = metrics.team || {};
            const successRate = (team.overall_success_rate * 100).toFixed(1);

            const html = `
                <div class="card team-health">
                    <h2>Team Health</h2>
                    <div class="health-bar">
                        <div class="bar">
                            <div class="bar-fill" style="width: ${successRate}%">
                                ${successRate >= 20 ? successRate + '%' : ''}
                            </div>
                        </div>
                        <div class="percentage">${successRate}%</div>
                    </div>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-label">Running Bots</div>
                            <div class="metric-value">${team.running_bots || 0}/${team.total_bots || 0}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Total Ticks</div>
                            <div class="metric-value">${team.total_ticks || 0}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Failed Ticks</div>
                            <div class="metric-value">${team.failed_ticks || 0}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Last Update</div>
                            <div class="metric-value" style="font-size: 12px;">
                                ${new Date(metrics.timestamp).toLocaleTimeString()}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="grid">
                    <div class="card">
                        <h2>Bot Status</h2>
                        <div class="bot-list">
                            ${renderBotList(metrics.bots || {})}
                        </div>
                    </div>
                    <div class="card">
                        <h2>System Metrics</h2>
                        <div class="system-metrics">
                            ${renderSystemMetrics(metrics.internal_metrics || {})}
                        </div>
                    </div>
                </div>

                ${metrics.alerts && metrics.alerts.length > 0 ? `
                    <div class="alerts">
                        <h3>⚠️ Alerts</h3>
                        ${metrics.alerts.map(alert => `<div class="alert-item">${alert}</div>`).join('')}
                    </div>
                ` : ''}
            `;

            document.getElementById('content').innerHTML = html;
        }

        function renderBotList(bots) {
            return Object.entries(bots).map(([name, data]) => `
                <div class="bot-item">
                    <div class="bot-name">${name}</div>
                    <div class="bot-status">
                        <span class="bot-dot ${data.running ? 'running' : ''}"></span>
                        <span>${data.running ? 'Running' : 'Stopped'}</span>
                    </div>
                    <div class="bot-stats">
                        <div class="stat">
                            <div class="stat-label">Ticks</div>
                            <div class="stat-value">${data.total_ticks || 0}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Success</div>
                            <div class="stat-value">${((data.success_rate || 0) * 100).toFixed(0)}%</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Passed</div>
                            <div class="stat-value">${data.passed_checks || 0}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Total</div>
                            <div class="stat-value">${data.total_checks || 0}</div>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function renderSystemMetrics(internal) {
            const counters = Object.entries(internal.counters || {});
            const gauges = Object.entries(internal.gauges || {});
            const items = [
                ...counters.map(([name, value]) => [`c:${name}`, value]),
                ...gauges.map(([name, value]) => [`g:${name}`, value]),
            ];

            if (!items.length) {
                return '<div class="metric-empty">No metrics yet</div>';
            }

            items.sort((a, b) => a[0].localeCompare(b[0]));
            return items.slice(0, 12).map(([name, value]) => `
                <div class="metric-row">
                    <div class="metric-name">${name}</div>
                    <div class="metric-value">${value}</div>
                </div>
            `).join('');
        }

        // Start connection
        connectWebSocket();
    </script>
</body>
</html>
"""
