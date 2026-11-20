"""
Test Suite: Phase 4 - Step 3 Verification
Focus: Multi-Container Orchestration, Volume Persistence, and Production Launch Scripts
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
from pathlib import Path
import yaml

def test_docker_compose_schema():
    print("Testing docker-compose.yml schema, services, and volume persistence...")
    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml does not exist!"

    content = compose_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "services" in data, "Must define 'services' block"
    services = data["services"]
    assert "backend" in services, "Must define 'backend' service"
    assert "frontend" in services, "Must define 'frontend' service"

    # Backend assertions
    backend = services["backend"]
    assert backend["build"]["context"] == "./backend", "Backend build context must be ./backend"
    assert backend["shm_size"] == "2gb", "Backend must allocate 2gb shared memory for Playwright stability"
    assert any("/app/data" in v for v in backend["volumes"]), "Backend must persist /app/data volume for multi-tenant vaults"
    assert any("/app/output" in v for v in backend["volumes"]), "Backend must persist /app/output volume for proof screenshots"
    assert "healthcheck" in backend, "Backend must define healthcheck"
    assert any("api/health" in s for s in backend["healthcheck"]["test"]), "Backend healthcheck must test /api/health"

    # Frontend assertions
    frontend = services["frontend"]
    assert frontend["build"]["context"] == "./frontend", "Frontend build context must be ./frontend"
    assert "backend" in frontend.get("depends_on", {}), "Frontend must depend on backend"
    assert frontend["depends_on"]["backend"]["condition"] == "service_healthy", "Frontend must wait for backend healthcheck"
    assert "healthcheck" in frontend, "Frontend must define healthcheck"
    assert any("healthz" in s for s in frontend["healthcheck"]["test"]), "Frontend healthcheck must test /healthz"

    # Network assertions
    assert "networks" in data, "Must define 'networks' block"
    assert "job_agent_network" in data["networks"], "Must define 'job_agent_network' bridge"
    print("✅ docker-compose.yml validated with complete production orchestration schema.")

def test_docker_compose_override_example():
    print("Testing docker-compose.override.yml.example...")
    override_path = Path(__file__).resolve().parent.parent / "docker-compose.override.yml.example"
    assert override_path.exists(), "docker-compose.override.yml.example does not exist!"
    content = override_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert "services" in data, "Override must define services"
    print("✅ docker-compose.override.yml.example validated.")

def test_launch_scripts():
    print("Testing start.sh and start.bat launch scripts...")
    sh_path = Path(__file__).resolve().parent.parent / "start.sh"
    bat_path = Path(__file__).resolve().parent.parent / "start.bat"

    assert sh_path.exists(), "start.sh missing!"
    assert bat_path.exists(), "start.bat missing!"

    # Strict POSIX LF check on Linux shell script
    sh_bytes = sh_path.read_bytes()
    assert not b"\r\n" in sh_bytes, "start.sh MUST have LF line endings (never CRLF)"
    sh_text = sh_bytes.decode("utf-8")
    assert "docker compose" in sh_text and "up -d --build" in sh_text, "start.sh must launch containers"

    bat_text = bat_path.read_text(encoding="utf-8")
    assert "docker compose up -d --build" in bat_text, "start.bat must launch containers"
    print("✅ start.sh and start.bat launch scripts validated.")

if __name__ == "__main__":
    print("=================================================================")
    print("Phase 4 - Step 3: Verification Suite")
    print("=================================================================")
    test_docker_compose_schema()
    test_docker_compose_override_example()
    test_launch_scripts()
    print("=================================================================")
    print("🏆 ALL PHASE 4 - STEP 3 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
