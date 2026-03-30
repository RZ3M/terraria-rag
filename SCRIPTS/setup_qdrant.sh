#!/usr/bin/env bash
# SCRIPTS/setup_qdrant.sh — Download and start Qdrant vector database.
#
# Qdrant is a local vector similarity search engine written in Rust.
# This script downloads the binary and starts it as a background service.
#
# Usage:
#   ./setup_qdrant.sh          # Download + start
#   ./setup_qdrant.sh --start  # Start only (if already downloaded)
#   ./setup_qdrant.sh --stop   # Stop the running instance
#   ./setup_qdrant.sh --status # Check if running

set -e

QDRANT_VERSION="1.7.4"
QDRANT_DIR="${HOME}/.local/qdrant"
QDRANT_BINARY="${QDRANT_DIR}/qdrant"
QDRANT_DATA_DIR="${HOME}/.local/qdrant_data"
QDRANT_LOG="${HOME}/.local/qdrant.log"
QDRANT_PORT="6333"

# Detect OS and architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "${ARCH}" in
    x86_64) ARCH="x86_64-unknown-linux-gnu" ;;
    aarch64|arm64) ARCH="aarch64-unknown-linux-gnu" ;;
    *) echo "Unsupported architecture: ${ARCH}"; exit 1 ;;
esac

QDRANT_URL="https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-${ARCH}-musl.tar.gz"

echo "==> Terraria RAG — Qdrant Setup"
echo "    OS: ${OS}, Arch: ${ARCH}"
echo "    Version: ${QDRANT_VERSION}"
echo "    Install dir: ${QDRANT_DIR}"
echo "    Data dir: ${QDRANT_DATA_DIR}"
echo ""

# Create directories
mkdir -p "${QDRANT_DIR}"
mkdir -p "${QDRANT_DATA_DIR}"

# Download if binary doesn't exist
if [ ! -f "${QDRANT_BINARY}" ]; then
    echo "==> Downloading Qdrant ${QDRANT_VERSION}..."
    TMP_ARCHIVE=$(mktemp)
    curl -L "${QDRANT_URL}" -o "${TMP_ARCHIVE}"
    echo "==> Extracting..."
    tar -xzf "${TMP_ARCHIVE}" -C "${QDRANT_DIR}"
    rm -f "${TMP_ARCHIVE}"
    # The archive contains 'qdrant' binary directly
    if [ ! -f "${QDRANT_DIR}/qdrant" ]; then
        # Find it
        FOUND=$(find "${QDRANT_DIR}" -name "qdrant" -type f 2>/dev/null | head -1)
        if [ -n "${FOUND}" ]; then
            mv "${FOUND}" "${QDRANT_BINARY}"
        fi
    fi
    chmod +x "${QDRANT_BINARY}"
    echo "    Downloaded and extracted."
else
    echo "==> Qdrant binary already exists. Skipping download."
fi

# Check if already running
is_running() {
    curl -s "http://localhost:${QDRANT_PORT}/readyz" > /dev/null 2>&1
}

case "${1:-}" in
    --start)
        echo "==> Starting Qdrant..."
        ;;
    --stop)
        echo "==> Stopping Qdrant..."
        pkill -f "qdrant" 2>/dev/null || true
        echo "    Stopped."
        exit 0
        ;;
    --status)
        if is_running; then
            echo "==> Qdrant is RUNNING on port ${QDRANT_PORT}"
            curl -s "http://localhost:${QDRANT_PORT}/readyz"
        else
            echo "==> Qdrant is NOT running"
            exit 1
        fi
        exit 0
        ;;
    "")
        # Default: start if not running
        if is_running; then
            echo "==> Qdrant is already running on port ${QDRANT_PORT}"
        else
            echo "==> Starting Qdrant in background..."
            nohup "${QDRANT_BINARY}" \
                --storage.storage_path="${QDRANT_DATA_DIR}" \
                --service.http_port="${QDRANT_PORT}" \
                > "${QDRANT_LOG}" 2>&1 &
            sleep 3
            if is_running; then
                echo "    Qdrant started successfully."
                echo "    HTTP:  http://localhost:${QDRANT_PORT}"
                echo "    gRPC:  localhost:6334"
                echo "    Log:   ${QDRANT_LOG}"
            else
                echo "    FAILED to start. Check ${QDRANT_LOG}"
                exit 1
            fi
        fi
        ;;
    *)
        echo "Usage: $0 [--start|--stop|--status]"
        exit 1
        ;;
esac
