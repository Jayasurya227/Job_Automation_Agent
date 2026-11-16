"""
Test Suite: Phase 4 - Step 2 Verification
Focus: Frontend Production Containerization, Multi-Stage Build, and Nginx SSE Proxy
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
import re
from pathlib import Path

def test_frontend_dockerfile():
    print("Testing frontend/Dockerfile multi-stage build syntax...")
    dockerfile_path = Path(__file__).resolve().parent.parent / "frontend" / "Dockerfile"
    assert dockerfile_path.exists(), "frontend/Dockerfile does not exist!"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "FROM node:20-alpine AS builder" in content, "Must use node:20-alpine builder stage"
    assert "npm ci" in content, "Must use npm ci for deterministic dependency installation"
    assert "npm run build" in content, "Must execute production build"
    assert "FROM nginx:1.27-alpine AS production" in content, "Must use nginx:1.27-alpine production stage"
    assert "COPY --from=builder /app/dist /usr/share/nginx/html" in content, "Must copy compiled dist artifacts"
    assert "EXPOSE 80" in content, "Must expose port 80"
    assert "HEALTHCHECK" in content and "/healthz" in content, "Must configure healthcheck against /healthz"
    print("✅ frontend/Dockerfile verified.")

def test_root_dockerfile_frontend():
    print("Testing root Dockerfile.frontend...")
    root_dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile.frontend"
    assert root_dockerfile.exists(), "Dockerfile.frontend does not exist at project root!"
    content = root_dockerfile.read_text(encoding="utf-8")

    assert "COPY frontend/package.json" in content, "Root Dockerfile must reference frontend/package.json"
    assert "COPY frontend/nginx.conf" in content, "Root Dockerfile must copy frontend/nginx.conf"
    assert "HEALTHCHECK" in content and "/healthz" in content, "Root Dockerfile must include healthcheck"
    print("✅ root Dockerfile.frontend verified.")

def test_frontend_dockerignore():
    print("Testing frontend/.dockerignore rules...")
    ignore_path = Path(__file__).resolve().parent.parent / "frontend" / ".dockerignore"
    assert ignore_path.exists(), "frontend/.dockerignore missing!"
    content = ignore_path.read_text(encoding="utf-8")

    assert "node_modules/" in content, "Must ignore node_modules"
    assert "dist/" in content, "Must ignore dist"
    assert ".git/" in content, "Must ignore .git"
    print("✅ frontend/.dockerignore verified.")

def test_nginx_configuration():
    print("Testing frontend/nginx.conf routing and SSE tuning...")
    nginx_path = Path(__file__).resolve().parent.parent / "frontend" / "nginx.conf"
    assert nginx_path.exists(), "frontend/nginx.conf missing!"
    content = nginx_path.read_text(encoding="utf-8")

    # Upstream definition
    assert "upstream backend_upstream" in content and "server backend:8000" in content, "Must define backend_upstream to backend:8000"

    # Resume upload body size
    assert "client_max_body_size 50M" in content, "Must allow 50M body size for PDF resumes"

    # Gzip & Security headers
    assert "gzip on" in content, "Must enable gzip compression"
    assert "X-Frame-Options" in content, "Must include X-Frame-Options security header"
    assert "X-Content-Type-Options" in content, "Must include X-Content-Type-Options security header"

    # Orchestrator Healthcheck
    assert "location = /healthz" in content and "return 200 'OK'" in content, "Must provide dedicated /healthz endpoint"

    # Zero-Buffering SSE Live Streaming
    assert "location = /api/events/stream" in content, "Must declare dedicated SSE stream location"
    assert "proxy_buffering off" in content, "SSE proxy MUST have proxy_buffering off"
    assert "proxy_cache off" in content, "SSE proxy MUST have proxy_cache off"
    assert "chunked_transfer_encoding on" in content, "SSE proxy MUST have chunked_transfer_encoding on"
    assert "proxy_read_timeout 86400s" in content, "SSE proxy MUST have long read timeout"

    # Gateway Routing
    assert "location /api/" in content and "proxy_pass http://backend_upstream/api/;" in content, "Must reverse proxy /api/ to backend_upstream"
    assert "location /output/" in content and "proxy_pass http://backend_upstream/output/;" in content, "Must reverse proxy /output/ to backend_upstream"
    assert "location /assets/" in content and "Cache-Control" in content, "Must provide immutable caching for static assets"

    # SPA Fallback
    assert "try_files $uri $uri/ /index.html" in content, "Must include SPA try_files fallback to /index.html"
    print("✅ frontend/nginx.conf conforms to enterprise reverse-proxy and SSE streaming standards.")

def test_frontend_dist_build():
    print("Testing frontend compiled dist directory...")
    dist_index = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    assert dist_index.exists(), "frontend/dist/index.html must exist from build stage"
    html_content = dist_index.read_text(encoding="utf-8")
    assert "<div id=\"root\"></div>" in html_content or "id=\"root\"" in html_content, "dist/index.html must contain root container"
    print("✅ frontend production bundle verified.")

if __name__ == "__main__":
    print("=================================================================")
    print("Phase 4 - Step 2: Verification Suite")
    print("=================================================================")
    test_frontend_dockerfile()
    test_root_dockerfile_frontend()
    test_frontend_dockerignore()
    test_nginx_configuration()
    test_frontend_dist_build()
    print("=================================================================")
    print("🏆 ALL PHASE 4 - STEP 2 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
