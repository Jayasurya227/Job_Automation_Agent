# <span style="color: #2563EB;">Full-Stack Architecture & Multi-Tenant Standards</span>

> **Core Objective**: Clear, actionable standards adapted from enterprise architecture rules to govern how our Multi-Tenant Frontend, Backend, Database, Task Queue, and Docker Microservices communicate securely and efficiently.

---

## <span style="color: #2563EB;">1. Isolated Directory & Vault Structure</span>

- **The Golden Rule**: Never mix client code, backend server code, or tenant-specific assets into a single shared folder.
- **Project Structure**:
  - `frontend/`: Contains only React 19 / Vite client code, HTML, CSS, and UI components. Runs in the user's browser or is served statically via Nginx.
  - `backend/`: Contains FastAPI routes, agent automation engines, database ORM logic, task queue, and security modules.
  - `backend/data/users/{user_id}/`: Physical **Per-User Storage Vaults** housing candidate-specific profiles, master resumes, persistent browser cookies, and proof screenshots.
  - `docs/`: System blueprints, architectural specifications, and implementation roadmaps.
- **Why It Matters**: Prevents accidental exposure of private database tokens, ensures absolute tenant data isolation, and enables independent containerization and horizontal scaling.

---

## <span style="color: #2563EB;">2. The Request-Response Lifecycle & Tenant Scoping</span>

- **No Direct Database Access**: The frontend NEVER directly touches the database or files.
- **Authenticated Bearer Communication**:
  - The frontend attaches a cryptographic JWT Bearer token to the `Authorization` header on every API call: `Authorization: Bearer <jwt_token>`.
  - The backend intercepts the token via `get_current_user`, validates the signature with `JWT_SECRET`, and extracts `current_user.id`.
- **Tenant-Scoped ORM Execution**:
  - Every database query automatically includes `WHERE user_id = current_user.id`.
  - Cross-tenant data viewing or modification is structurally blocked at the database engine level.
- **Standardized JSON Exchange**:
  - All request and response bodies use strict Pydantic v2 schemas.
  - Errors return RFC 7807 compliant JSON error payloads with clear status codes (`401 Unauthorized`, `403 Forbidden`, `404 Not Found`).

---

## <span style="color: #2563EB;">3. Security Boundaries & Secrets Protection</span>

- **The Client is Public**: Any JavaScript file served to the browser can be inspected via DevTools. Never embed secrets in frontend code.
- **Strict Environment Separation**:
  - **Private Server Secrets**: `ANTHROPIC_API_KEY`, `JWT_SECRET`, database connection strings, and portal passwords live strictly in `backend/.env` (or Docker environment variables).
  - **Zero Key Leakage**: No private API keys or auth tokens are prefixed with `VITE_` or exposed to public bundles.
- **Path Traversal Protection**:
  - File serving endpoints (`/output/` and `/api/jobs/{id}/resume`) sanitize all path inputs, verifying that requested file paths strictly resolve inside the authenticated candidate's assigned vault (`backend/data/users/{current_user.id}/`).

---

## <span style="color: #2563EB;">4. CORS & Reverse Proxy Standards</span>

- **Development Mode**:
  - When running locally (FastAPI on `:8000`, Vite on `:5173`), FastAPI's `CORSMiddleware` whitelists `http://localhost:5173` with explicit allowed headers (`Authorization`, `Content-Type`) and methods (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`).
- **Production Docker Mode**:
  - **Nginx Reverse Proxy** unifies frontend and backend under a single host and port (`:5173` or `:80`).
  - Browser requests to `/api/*` and `/output/*` are proxied internally to `http://backend:8000/`, eliminating cross-origin browser restrictions and maximizing network throughput.

---

## <span style="color: #2563EB;">5. Real-Time Telemetry & SSE Zero-Buffering Standard</span>

- **Anti-Eavesdropping EventBus**:
  - Server-Sent Events (`/api/events/stream`) stream live job execution telemetry and logs.
  - The EventBus enforces `user_id` filtering so User A's browser receives only User A's discovery and application events.
- **Nginx SSE Streaming Configuration**:
  - Because Nginx buffers HTTP responses by default, streaming SSE connections require explicit proxy buffering overrides:
    ```nginx
    location /api/events/stream {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
        proxy_read_timeout 86400s;
    }
    ```

---

## <span style="color: #2563EB;">6. Tenant-Level Isolation & Privacy Guard</span>

- **Independent Session Vaults**:
  - Persistent Chromium cookies and browser contexts are saved per user: `data/users/{user_id}/browser_session/`.
  - Logging out or disconnecting Naukri for User B deletes only User B's session directory, leaving User A's authenticated session completely unaffected.
- **Zero-Theft Resume Guard**:
  - Resumes are streamed directly from `data/users/{user_id}/uploaded_resume.pdf` into portal upload containers. The agent never cross-references or falls back to another user's documents.
- **Master User Deletion Shield**:
  - The platform implements a permanent deletion shield protecting the primary administrator (`Rayavaram Jayasurya`, `user_id = 1`) against accidental or programmatic deletion during multi-tenant cleanups.

---

## <span style="color: #2563EB;">7. DevOps Containerization & Orchestration Standard</span>

- **Non-Root Execution**:
  - The backend Docker container creates and executes under a dedicated non-privileged user (`appuser:1001`), adhering to enterprise security compliance.
- **Chromium Shared Memory Allocation**:
  - Playwright requires sufficient shared memory to run headless Chromium without crashing. Docker Compose explicitly allocates:
    ```yaml
    shm_size: 2gb
    ```
- **Volume Mounts & Data Persistence**:
  - Persistent host volumes ensure database records and user storage vaults survive container restarts and image rebuilds:
    ```yaml
    volumes:
      - ./backend/data:/app/data
      - ./backend/output:/app/output
    ```
- **Automated Healthchecks**:
  - Frontend serves `/healthz` via Nginx.
  - Backend exposes `/api/health` returning JSON health telemetry.

---

## <span style="color: #2563EB;">8. Technical Interview Defense Guide</span>

Key questions interviewers ask about this architecture and how to answer them:

- **Q: How does the system guarantee tenant data privacy across multiple candidates?**
  - *Answer*: We enforce defense-in-depth across three tiers: (1) Cryptographic JWT authentication, (2) Row-level database filtering enforcing `WHERE user_id = current_user.id` on all SQLAlchemy queries, and (3) Physical per-user storage vaults (`data/users/{uid}/`) isolating resumes, browser cookies, and proof screenshots.
- **Q: How do you handle concurrent browser automation tasks without blocking the server?**
  - *Answer*: We engineered an asynchronous `MultiTenantTaskQueue` with per-user `asyncio.Lock()` instances. Worker coroutines execute discovery and application tasks concurrently, ensuring User A's crawl does not block or delay User B's workflow.
- **Q: Why does the Docker Compose configuration specify `shm_size: 2gb`?**
  - *Answer*: Headless Chromium relies heavily on `/dev/shm` for shared memory and graphics rendering. The default Docker shared memory size (64MB) frequently causes browser crashes during intensive DOM interactions; allocating 2GB ensures stable, long-running Playwright execution.
- **Q: How did you configure Nginx to support Server-Sent Events (SSE)?**
  - *Answer*: By default, Nginx buffers upstream responses, which stalls real-time event streaming. We configured `proxy_buffering off`, `proxy_cache off`, and `chunked_transfer_encoding on` with extended timeouts for `/api/events/stream`.
- **Q: Can the platform switch from SQLite to PostgreSQL in production?**
  - *Answer*: Yes. We use SQLAlchemy 2.0 ORM with dialect-agnostic models. The system defaults to embedded multi-tenant SQLite with WAL mode enabled for zero-config deployments, but setting `DATABASE_URL=postgresql://...` instantly switches the platform to PostgreSQL with zero code changes.

---
