"""Health check module for the FFC framework."""
import http.server
import json
import os
import threading
from typing import Optional

import psutil


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # pylint: disable=invalid-name
        if self.path == "/health":
            health_status = self._check_health()
            self.send_response(200 if health_status["status"] == "healthy" else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health_status).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _check_health(self):
        """Check various health metrics."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "status": "healthy",
            "version": os.getenv("FFC_VERSION", "unknown"),
            "metrics": {
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
                "thread_count": process.num_threads(),
                "open_files": len(process.open_files()),
            },
        }

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class HealthCheck:
    def __init__(self, port: int = 8080):
        self.port = port
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the health check server in a background thread."""
        if self._server is not None:
            return

        self._server = http.server.HTTPServer(
            ("0.0.0.0", self.port), HealthCheckHandler
        )
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """Stop the health check server."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
