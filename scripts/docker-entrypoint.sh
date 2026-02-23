#!/bin/bash
set -e

# Initialize D-Bus session if not running
# This is required for gnome-keyring to function in a headless environment
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
    export DBUS_SESSION_BUS_PID
fi

# Ensure config directory exists
mkdir -p /root/.nanofolks

# Handle commands
if [ "$1" = "bridge" ]; then
    echo "Starting WhatsApp bridge..."
    cd /app/bridge
    exec npm start
elif [ "$1" = "shell" ]; then
    exec /bin/bash
else
    # Default: Run the nanofolks CLI
    # If no arguments, it will fall back to "nanofolks status" via Docker CMD
    exec nanofolks "$@"
fi
