"""
Test Suite: Phase 4 - Step 1 Verification
Focus: Backend Docker Containerization, Security Hardening, and Dependency Completeness
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
import os
import re
from pathlib import Path

def test_backend_dockerfile():
    print("Testing backend/Dockerfile syntax and hardening...")
    dockerfile_path = Path(__file__).resolve().parent / "Dockerfile"
    assert dockerfile_path.exists(), "backend/Dockerfile does not exist!"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "python:3.11-slim" in content, "Must use python 3.11 slim base image"
    assert "PLAYWRIGHT_BROWSERS_PATH=/ms-playwright" in content, "Must set centralized PLAYWRIGHT_BROWSERS_PATH"
    assert "playwright install --with-deps chromium" in content, "Must install Playwright Chromium with system dependencies"
    assert "appuser" in content and "1001" in content, "Must configure non-root appuser with UID 1001"
    assert "VOLUME" in content and "/app/data" in content, "Must declare volume mount for /app/data"
    assert "EXPOSE 8000" in content, "Must expose port 8000"
    assert "HEALTHCHECK" in content and "/api/health" in content, "Must configure container healthcheck against /api/health"
    assert "ENTRYPOINT" in content, "Must have an entrypoint script"
    assert "CMD" in content and "uvicorn" in content, "Must specify uvicorn startup command"
    print("✅ backend/Dockerfile conforms to production architecture standards.")

def test_root_dockerfile_backend():
    print("Testing root Dockerfile.backend...")
    root_dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile.backend"
    assert root_dockerfile.exists(), "Dockerfile.backend does not exist at project root!"
    content = root_dockerfile.read_text(encoding="utf-8")

    assert "COPY backend/requirements.txt" in content, "Root Dockerfile must reference backend/requirements.txt"
    assert "COPY backend/ /app/" in content, "Root Dockerfile must copy backend/ directory"
    assert "HEALTHCHECK" in content, "Root Dockerfile must include healthcheck"
    print("✅ root Dockerfile.backend verified.")

def test_dockerignore_rules():
    print("Testing .dockerignore hygiene...")
    backend_ignore = Path(__file__).resolve().parent / ".dockerignore"
    root_ignore = Path(__file__).resolve().parent.parent / ".dockerignore"

    assert backend_ignore.exists(), "backend/.dockerignore missing!"
    assert root_ignore.exists(), "root .dockerignore missing!"

    backend_text = backend_ignore.read_text(encoding="utf-8")
    assert "venv/" in backend_text, "Must ignore venv"
    assert ".env" in backend_text, "Must ignore .env secrets"
    assert "__pycache__/" in backend_text, "Must ignore python cache"
    assert "browser_session/" in backend_text, "Must ignore local browser session caches"

    root_text = root_ignore.read_text(encoding="utf-8")
    assert "node_modules/" in root_text, "Root must ignore node_modules"
    assert "venv/" in root_text, "Root must ignore venv"
    print("✅ .dockerignore rules verified.")

def test_requirements_completeness():
    print("Testing requirements.txt multi-tenant & crypto dependencies...")
    req_path = Path(__file__).resolve().parent / "requirements.txt"
    req_text = req_path.read_text(encoding="utf-8")

    expected_pkgs = [
        "anthropic", "pydantic", "fastapi", "uvicorn", "playwright",
        "bcrypt", "pyjwt", "cryptography", "aiosqlite", "sqlalchemy"
    ]
    for pkg in expected_pkgs:
        assert re.search(rf"^{pkg}", req_text, re.MULTILINE | re.IGNORECASE), f"Missing critical dependency: {pkg}"
    print(f"✅ All {len(expected_pkgs)} critical dependencies present in requirements.txt.")

def test_docker_entrypoint():
    print("Testing backend/docker-entrypoint.sh formatting...")
    entrypoint_path = Path(__file__).resolve().parent / "docker-entrypoint.sh"
    assert entrypoint_path.exists(), "backend/docker-entrypoint.sh missing!"
    raw_bytes = entrypoint_path.read_bytes()

    assert not b"\r\n" in raw_bytes, "docker-entrypoint.sh MUST NOT have Windows CRLF line endings (must be LF only)"
    content = raw_bytes.decode("utf-8")
    assert content.startswith("#!/bin/sh"), "Must start with #!/bin/sh"
    assert 'exec "$@"' in content, "Must have exec \"$@\" for process signal forwarding"
    print("✅ backend/docker-entrypoint.sh verified with strict POSIX LF formatting.")

def test_docker_env_example():
    print("Testing .env.docker.example configuration...")
    env_example = Path(__file__).resolve().parent.parent / ".env.docker.example"
    assert env_example.exists(), ".env.docker.example missing!"
    text = env_example.read_text(encoding="utf-8")

    assert "ANTHROPIC_API_KEY" in text, "Missing ANTHROPIC_API_KEY in example"
    assert "SECRET_KEY" in text, "Missing SECRET_KEY in example"
    assert "DATABASE_URL" in text, "Missing DATABASE_URL in example"
    print("✅ .env.docker.example verified.")

if __name__ == "__main__":
    print("=================================================================")
    print("Phase 4 - Step 1: Verification Suite")
    print("=================================================================")
    test_backend_dockerfile()
    test_root_dockerfile_backend()
    test_dockerignore_rules()
    test_requirements_completeness()
    test_docker_entrypoint()
    test_docker_env_example()
    print("=================================================================")
    print("🏆 ALL PHASE 4 - STEP 1 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
