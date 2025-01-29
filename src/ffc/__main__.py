"""Main entry point for the FFC framework."""
import os
import signal
import sys

from ffc.core.health import HealthCheck
from ffc.core.logging import get_logger, setup_logging

# Set up logging
setup_logging(
    log_level=os.getenv("FFC_LOG_LEVEL", "INFO"),
    log_file=os.getenv("FFC_LOG_FILE"),
    max_bytes=int(os.getenv("FFC_LOG_MAX_BYTES", 10 * 1024 * 1024)),
    backup_count=int(os.getenv("FFC_LOG_BACKUP_COUNT", 5)),
)

logger = get_logger(__name__)


def main():
    """Main entry point."""
    logger.info(
        "Starting FFC framework", extra={"version": os.getenv("FFC_VERSION", "unknown")}
    )

    # Start health check server
    health_check = HealthCheck()
    health_check.start()
    logger.info("Health check server started", extra={"port": 8080})

    # Set up signal handlers
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal", extra={"signal": signum})
        health_check.stop()
        logger.info("Health check server stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Your main application logic here
        # For now, just keep the process running
        logger.info("FFC framework running")
        signal.pause()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        health_check.stop()
        logger.info("Health check server stopped")
        sys.exit(0)
    except Exception as e:
        logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
        health_check.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
