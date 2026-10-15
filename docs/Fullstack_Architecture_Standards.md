# <span style="color: #2563EB;">Full-Stack Architecture & Communication Standards</span>

> **Core Objective**: Clear, actionable standards adapted from enterprise architecture rules to govern how our Frontend, Backend, Database, and APIs communicate securely and efficiently.

---

## <span style="color: #2563EB;">1. Isolated Directory Structure</span>

- **The Golden Rule**: Never mix frontend client code with backend server code into a single folder.
- **Our Project Layout**:
  - `frontend/`: Contains only user interface code (React/Vite, HTML, CSS, client-side routing, dashboard components). Runs publicly in the user's browser.
  - `backend/`: Contains FastAPI routes, LangGraph orchestration, Playwright automation, SQLite database logic, and secret keys. Runs securely on the host machine.
  - `docs/`: Contains all system design blueprints, specifications, and architecture guides.
- **Why It Matters**: Prevents accidental exposure of private database tokens, keeps dependencies strictly separated, and allows independent testing and deployment.

---

## <span style="color: #2563EB;">2. The Request-Response Lifecycle</span>

- **No Direct Database Access**: The Frontend NEVER directly touches the SQLite database or backend files.
- **Asynchronous HTTP Communication**:
  - The Frontend fires asynchronous network calls (`fetch` or `axios`) over HTTP/HTTPS to explicit backend endpoints.
  - The Backend intercepts the request, validates the input with Pydantic, queries SQLite, executes Gemini/Playwright, and responds.
- **Standardized JSON Exchange**:
  - All communication is strictly formatted in structured JSON.
  - *Example Request (Analyze Job)*:
    - Frontend sends: `POST /api/analyze` with `{ "job_description": "We need Python, FastAPI..." }`
  - *Example Response*:
    - Backend replies: `200 OK` with `{ "status": "success", "match_score": 88, "resume_url": "/output/google_resume.pdf" }`
- **Dynamic UI Re-rendering**: The Frontend parses the incoming JSON payload and immediately updates the dashboard screen without reloading the page.

---

## <span style="color: #2563EB;">3. Security Boundaries & Secrets Protection</span>

- **The Client is Public**: Any code inside `frontend/` (including JavaScript bundles and public variables) can be inspected by anyone using browser DevTools.
- **Strict Environment Separation**:
  - **Private Secrets**: `GEMINI_API_KEY`, `GMAIL_APP_PASSWORD`, and database file paths must live ONLY in `backend/.env`.
  - **Public Variables**: The frontend only stores the backend URL (e.g., `VITE_API_BASE_URL=http://localhost:8000`).
- **Never Leak Keys**: Never prefix private API keys with public tags (`REACT_APP_` or `VITE_`). The frontend should never know your Gemini key exists.

---

## <span style="color: #2563EB;">4. CORS (Cross-Origin Resource Sharing) Policy</span>

- **The Browser Security Block**:
  - When the Frontend runs on `http://localhost:5173` (Vite) and the Backend runs on `http://localhost:8000` (FastAPI), the browser treats them as different origins and blocks requests by default.
- **FastAPI CORS Configuration**:
  - The backend explicitly sends CORS headers permitting requests from the frontend origin:
    - `Access-Control-Allow-Origin: http://localhost:5173`
    - Allowed methods: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`.
- **Note**: CORS is browser-level domain permission, not user authentication.

---

## <span style="color: #2563EB;">5. Server Failure & Offline Resilience</span>

- **Independent Infrastructure**:
  - If the backend engine or automation process temporarily stops, the Frontend UI does not vanish or crash.
  - Static HTML/CSS pages still load cleanly from the local web server or CDN.
- **Graceful Error Handling**:
  - When an API request fails (e.g., backend offline or network dropped), the frontend must display a friendly fallback banner:
    - *"Backend engine offline. Please start the server or verify connection."*
  - The app should never show a blank white screen or raw terminal crash dump to the user.

---

## <span style="color: #2563EB;">6. Git Branching & Development Workflow</span>

- **Main Branch (`main`)**: Reserved strictly for tested, working production code.
- **Feature Branches**: Every new component is built on an isolated branch before merging:
  - `feature/ai-brain-matcher` (Phase 1)
  - `feature/sqlite-dashboard` (Phase 2)
  - `feature/playwright-scraper` (Phase 3)
  - `feature/langgraph-orchestrator` (Phase 4)
- **Why It Matters**: Prevents experimental, buggy code from breaking working features.

---

## <span style="color: #2563EB;">7. Technical Interview Defense Guide</span>

Key questions interviewers ask about this architecture and how to answer them:

- **Q: How do your frontend and backend communicate?**
  - *Answer*: Through asynchronous RESTful HTTP requests using JSON payloads. The frontend never accesses files or the database directly; it communicates exclusively through FastAPI endpoints.
- **Q: Where are your sensitive AI keys stored?**
  - *Answer*: Strictly on the server side in a protected `backend/.env` file. The frontend client bundle contains zero API keys or database tokens.
- **Q: What is CORS and how did you resolve it?**
  - *Answer*: CORS is a browser security mechanism that prevents unauthorized cross-origin requests. In FastAPI, I configured `CORSMiddleware` to explicitly whitelist our frontend origin (`http://localhost:5173`).
- **Q: What happens if the backend crashes while a user is on the site?**
  - *Answer*: The frontend UI remains operational. API calls catch network errors and display an informative fallback state rather than crashing the interface.

---
