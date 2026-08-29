#!/usr/bin/env bash

set -euo pipefail

uv run --group frontend streamlit run \
    deployment/frontend/app.py \
    --server.headless=true \
    --server.port=8501 \
    > /tmp/streamlit.log 2>&1 &

STREAMLIT_PID=$!

cleanup() {
    echo "Stopping Streamlit process: $STREAMLIT_PID"

    pkill -TERM -P "$STREAMLIT_PID" 2>/dev/null || true
    kill "$STREAMLIT_PID" 2>/dev/null || true

    sleep 1

    pkill -KILL -P "$STREAMLIT_PID" 2>/dev/null || true
    kill -KILL "$STREAMLIT_PID" 2>/dev/null || true
}

trap cleanup EXIT

for i in {1..30}; do
    if curl \
        --fail \
        --silent \
        http://localhost:8501 \
        > /dev/null
    then
        echo "Streamlit started successfully."
        exit 0
    fi

    sleep 1
done

echo "Streamlit failed to start."

cat /tmp/streamlit.log

exit 1