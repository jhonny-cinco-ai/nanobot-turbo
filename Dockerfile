# Multi-stage build for nanofolks
# Stage 1: Build Python wheel with dependencies
# Stage 2: Build WhatsApp bridge
# Stage 3: Final runtime image (minimal)

# =============================================================================
# Stage 1: Python Builder
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY pyproject.toml README.md LICENSE ./
COPY nanofolks/ nanofolks/

# Create empty bridge directory (referenced in pyproject.toml but built separately)
RUN mkdir -p bridge && touch bridge/.gitkeep

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    mkdir -p /wheels && \
    cp dist/*.whl /wheels/

# =============================================================================
# Stage 2: WhatsApp Bridge Builder
# =============================================================================
FROM node:20-slim AS bridge-builder

WORKDIR /build

# Install git and ca-certificates (required for npm dependencies)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Configure git to use https instead of ssh for GitHub
RUN git config --global url."https://github.com/".insteadOf ssh://git@github.com/

# Copy bridge files
COPY bridge/package.json bridge/tsconfig.json ./
COPY bridge/src/ src/

# Install dependencies and build
RUN npm install && npm run build

# =============================================================================
# Stage 3: Runtime
# =============================================================================
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Install runtime dependencies (minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        gnome-keyring \
        libdbus-glib-1-2 \
        dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

# Create config directory
RUN mkdir -p /root/.nanofolks

# Copy and install Python wheel with all dependencies
COPY --from=python-builder /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm /tmp/*.whl && \
    rm -rf /root/.cache/pip

# Copy WhatsApp bridge runtime files only
COPY --from=bridge-builder /build/dist ./bridge/dist
COPY --from=bridge-builder /build/node_modules ./bridge/node_modules
COPY --from=bridge-builder /build/package.json ./bridge/

# Add entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Gateway port
EXPOSE 18790

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["status"]

