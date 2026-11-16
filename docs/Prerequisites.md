# <span style="color: #2563EB;">Project Prerequisites & System Requirements</span>

> A clear, comprehensive guide detailing every technology, tool, and runtime environment required to run, build, and deploy the Autonomous Job Automation Agent (Multi-User SaaS).

---

## <span style="color: #2563EB;">1. Core Tech Stack</span>

### **Python (v3.12+)**
- **What it is**: High-performance backend programming language.
- **Why we use it**: Powers FastAPI, Playwright browser automation, Anthropic Claude AI integration, and the concurrent task queue.

### **Node.js (v20+) & Vite**
- **What it is**: Modern JavaScript runtime and build engine.
- **Why we use it**: Compiles and serves the React 19 frontend application with hot module replacement (HMR) and optimized static production builds.

### **Docker & Docker Compose**
- **What it is**: Industry-standard containerization platform.
- **Why we use it**: Packages the entire full-stack platform into reproducible, isolated microservices (`backend` and `frontend`). Enables one-command launch across any OS or cloud VM.

### **Nginx 1.27 (Alpine)**
- **What it is**: High-performance web server and reverse proxy.
- **Why we use it**: Serves production React assets, proxies API calls to FastAPI, mounts tenant output vaults securely, and streams real-time Server-Sent Events (SSE) with zero-buffering.

### **Dual-Engine Database (SQLite WAL / PostgreSQL)**
- **What it is**: SQLAlchemy 2.0 ORM with dialect-agnostic models.
- **Why we use it**: Defaults to embedded multi-tenant SQLite with Write-Ahead Logging (WAL) and foreign keys enabled for zero-config local operation. Supports Cloud PostgreSQL (`DATABASE_URL=postgresql://...`) with 0 code changes.

---

## <span style="color: #2563EB;">2. Security & Automation Libraries</span>

### **Playwright (Chromium Engine)**
- **What it is**: Modern, high-speed browser automation framework.
- **Why we use it**: Drives stealth multi-page job searches on Naukri.com, solves dynamic screening drawers, simulates human typing jitter, and captures proof snapshots.

### **Cryptographic Security (`bcrypt` & `PyJWT`)**
- **What it is**: Industry-standard password hashing and JWT token management.
- **Why we use it**: Protects candidate credentials with secure salt rounds and signs Bearer JWT tokens to enforce strict tenant isolation across all API endpoints.

### **Pydantic v2**
- **What it is**: Data validation and settings management library.
- **Why we use it**: Enforces strict typing and structure for all incoming API payloads, AI responses, and database schemas.

---

## <span style="color: #2563EB;">3. External APIs & Portal Credentials</span>

### **Anthropic Claude API Key**
- **What it is**: Developer API key from [Anthropic Console](https://console.anthropic.com/).
- **Why we use it**: Powers our AI Brain using **Claude 3.5 Haiku (`claude-haiku-5-5`)** for sub-second, zero-hallucination ATS match scoring and technical screening MCQ resolution.

### **Naukri.com Account (Candidate Account)**
- **What it is**: Candidate profile on Naukri.com.
- **Why we use it**: Target job portal for automated search and 1-click applications. Authenticated once via headless mobile OTP and preserved inside the candidate's isolated session vault.

### **Gmail App Password (Optional Outreach Engine)**
- **What it is**: 16-character application-specific password generated inside your Google Account.
- **Why we use it**: Enables Python to send personalized recruiter outreach emails via standard Gmail SMTP.

---

## <span style="color: #2563EB;">4. Candidate Master Assets (Per-User Storage Vault)</span>

Inside `backend/data/users/{user_id}/`:
- **Master PDF Resume (`uploaded_resume.pdf`)**: The baseline resume uploaded by the candidate and streamed directly to job portal containers.
- **Master Profile (`profile.json`)**: Candidate personal facts, verified work history, target roles, and ATS match thresholds.

---
