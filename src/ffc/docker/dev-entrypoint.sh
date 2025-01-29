#!/bin/bash
set -e

# Start debugpy server if DEBUG is set
if [ "${ENABLE_DEBUGGER}" = "true" ]; then
    echo "Starting debugpy server on port 5678"
    python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m ffc.agent.runner
else
    # Start the application with hot reload using watchdog
    python -m watchdog.watchmedo auto-restart \
        --patterns="*.py" \
        --recursive \
        --directory="/app" \
        -- python -m ffc.agent.runner
fi
