#!/usr/bin/env bash
set -euo pipefail

# RedOps Eval — Bootstrap Script
# Initializes the development environment after cloning.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Setting up RedOps Eval development environment..."

# Copy .env.example if .env doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "    Created .env from .env.example"
fi

# Install backend dependencies
echo "==> Installing backend dependencies..."
cd "$PROJECT_DIR/backend"
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Install frontend dependencies
echo "==> Installing frontend dependencies..."
cd "$PROJECT_DIR/frontend"
npm install

echo ""
echo "==> RedOps Eval is ready!"
echo ""
echo "    Start the application:"
echo "        docker compose -f docker/docker-compose.yml up"
echo ""
echo "    API:        http://localhost:8000"
echo "    Docs:       http://localhost:8000/docs"
echo "    Frontend:   http://localhost:5173"
echo "    Temporal:   http://localhost:8233"
echo ""
