#!/bin/sh
set -e

# ==============================================================================
# Autonomous Job Automation Agent - Backend Container Entrypoint
# Production Security & Runtime Pre-flight Initializer
# ==============================================================================

# Ensure storage vaults and output directories exist
mkdir -p /app/data/users /app/output

# Execute main container command (replaces shell with child process for clean signal propagation)
exec "$@"
