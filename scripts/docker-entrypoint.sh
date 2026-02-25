#!/bin/bash
set -e

# Initialize D-Bus session if not running
# This is required for gnome-keyring to function in a headless environment
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax)
    export DBUS_SESSION_BUS_ADDRESS
    export DBUS_SESSION_BUS_PID
fi

# Auto-initialize and unlock keyring for Docker environment (opt-in)
# Set NANOFOLKS_KEYRING_PASSWORD to enable; otherwise skip.
if [ "$1" != "bridge" ] && [ "$1" != "shell" ]; then
    if [ -n "$NANOFOLKS_KEYRING_PASSWORD" ]; then
        echo "Initializing container keyring..."
        # Start gnome-keyring-daemon, unlock it, and export session variables
        eval $(echo "$NANOFOLKS_KEYRING_PASSWORD" | gnome-keyring-daemon --unlock --components=secrets --daemonize)
        export GNOME_KEYRING_CONTROL
        export GNOME_KEYRING_PID
    else
        echo "Skipping keyring unlock (set NANOFOLKS_KEYRING_PASSWORD to enable)."
    fi
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
