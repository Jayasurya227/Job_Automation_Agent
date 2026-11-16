#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Autonomous AI Job Application Agent - Production Launch Script (Linux/Cloud VM)
# ==============================================================================

echo "====================================================================="
echo "🚀 Launching Autonomous Job Automation Agent (Multi-User SaaS Stack)"
echo "====================================================================="

# Check environment configuration
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Initializing from .env.docker.example..."
    cp .env.docker.example .env
    echo "ℹ️  Created .env. Please update your ANTHROPIC_API_KEY in .env if needed."
fi

# Ensure data directories exist on host
mkdir -p backend/data/users backend/output

# Detect docker compose CLI version
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Error: Docker / Docker Compose is not installed or not in PATH."
    exit 1
fi

echo "📦 Building and starting multi-tenant microservices in detached mode..."
$COMPOSE_CMD up -d --build

echo "---------------------------------------------------------------------"
echo "✅ Stack successfully launched!"
echo "🌐 Frontend Dashboard: http://localhost:${FRONTEND_PORT:-80}"
echo "🔌 Backend API Docs:   http://localhost:${BACKEND_PORT:-8000}/docs"
echo "💓 Backend Health:     http://localhost:${BACKEND_PORT:-8000}/api/health"
echo "====================================================================="
