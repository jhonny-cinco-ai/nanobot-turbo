#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

IMAGE_NAME="nanofolks-test"

echo "=== Building Docker image ==="
docker build -t "$IMAGE_NAME" .

echo ""
echo "=== Running 'nanofolks onboard' ==="
docker run --name nanofolks-test-run "$IMAGE_NAME" onboard --non-interactive

echo ""
echo "=== Running 'nanofolks status' ==="
STATUS_OUTPUT=$(docker commit nanofolks-test-run nanofolks-test-onboarded > /dev/null && \
    docker run --rm nanofolks-test-onboarded status 2>&1) || true

echo "$STATUS_OUTPUT"

echo ""
echo "=== Validating output ==="
PASS=true

check() {
    if echo "$STATUS_OUTPUT" | grep -q "$1"; then
        echo "  PASS: found '$1'"
    else
        echo "  FAIL: missing '$1'"
        PASS=false
    fi
}

check "nanofolks Status"
check "Config:"
check "Workspace:"
check "Model:"
check "OpenRouter:"
check "Anthropic:"
check "OpenAI:"

echo ""
if $PASS; then
    echo "=== All checks passed ==="
else
    echo "=== Some checks FAILED ==="
    exit 1
fi

# Cleanup
echo ""
echo "=== Cleanup ==="
docker rm -f nanofolks-test-run 2>/dev/null || true
docker rmi -f nanofolks-test-onboarded 2>/dev/null || true
docker rmi -f "$IMAGE_NAME" 2>/dev/null || true
echo "Done."
