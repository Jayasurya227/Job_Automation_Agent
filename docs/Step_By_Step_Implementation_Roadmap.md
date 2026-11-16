# Step-by-Step Implementation Roadmap: Autonomous Job Agent

> **Guiding Philosophy & Principal Engineer Mindset**  
> Professional software engineers build complex systems one verified, testable block at a time.  
> Following this phase-by-phase roadmap, every milestone produced a standalone, production-grade deliverable adhering strictly to the Principal Engineer Mandates below.

---

## High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│             REVERSE PROXY & GATEWAY (Nginx Alpine :5173 / :80)         │
│     • Static React 19 SPA    • /api/ Reverse Proxy                     │
│     • Zero-Buffering SSE     • /output/ User Vault Static Mount        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP / SSE Stream
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│             BACKEND APPLICATION SERVER (FastAPI :8000)                 │
│     • JWT & bcrypt Auth Engine   • Row-Level Tenant Isolation          │
│     • Dual-Engine DB (SQLite/PG) • Multi-Tenant SSE EventBus           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│        CONCURRENT TASK QUEUE (MultiTenantTaskQueue & asyncio.Lock)     │
│     • Independent Per-User Worker Pools • Anti-Collision Locks         │
│     • User-Scoped Timetable Cadence     • Daily Quota Counter          │
└──────────────┬───────────────────┬───────────────────┬─────────────────┘
               │                   │                   │
               ▼                   ▼                   ▼
    ┌────────────────────┐ ┌───────────────┐ ┌───────────────────┐
    │    THE AI BRAIN    │ │ NAUKRI STEALTH│ │ RECRUITER OUTREACH│
    │(Anthropic Claude)  │ │ (Playwright)  │ │   (Gmail SMTP)    │
    │- ATS Match Scorer  │ │- Stealth Crawl│ │- Recruiter Search │
    │- Skill Gap Analysis│ │- 1-Click Apply│ │- Cold Email Draft │
    │- MCQ Chatbot Solver│ │- Fresher Skip │ │- Quota Enforcer   │
    └────────────────────┘ └───────────────┘ └───────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│            TENANT PERSISTENCE & STORAGE VAULTS LAYER                   │
│     • data/users/{uid}/profile.json        (Candidate facts)           │
│     • data/users/{uid}/uploaded_resume.pdf (Master PDF resume)         │
│     • data/users/{uid}/browser_session/    (Stealth Naukri cookies)    │
│     • data/users/{uid}/output/snapshots/   (Visual proof captures)     │
│     • jobs.db / Cloud PostgreSQL           (Row-level tenant records)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Principal Engineer Coding Mandates (The 7 Non-Negotiable Rules)

### Rule 1: Zero Blind Trust in AI Code (20–30 Years Senior Experience Mindset)
- Never accept AI-generated boilerplate blindly. Scrutinize every loop, query, and API call for resource leaks, deadlocks, and edge cases before adoption.

### Rule 2: Hardcore Production Security (Zero Vulnerabilities)
- Passwords hashed with `bcrypt`. JWT tokens cryptographically signed. Private secrets strictly in `.env`. Strict Pydantic v2 input validation on every endpoint.

### Rule 3: Low Code with High Accuracy (Zero Bloat)
- Avoid verbose boilerplate. Prioritize clean, expressive, modular code where every module has a single responsibility.

### Rule 4: Strict Enterprise Directory Layout
- Absolute separation between client UI (`frontend/`), server logic (`backend/app/`), tenant storage vaults (`backend/data/users/{uid}/`), and DevOps manifests.

### Rule 5: Built From Scratch to Production Standard
- Every schema, ORM relationship, crawler loop, and task queue is constructed step-by-step from foundational first principles.

### Rule 6: Tenant Data Isolation & Privacy Guard
- Zero cross-tenant data bleed. Every database query enforces `WHERE user_id = current_user.id`. Resumes, browser cookies, and telemetry streams are partitioned per user.

### Rule 7: DevOps Containerization & Portability
- Microservices packaged in Docker Compose with non-root security (`appuser:1001`), Nginx reverse proxy, shared memory allocation (`shm_size: 2gb`) for Chromium, and persistent data volume mounts.

---

## Phase 1: Foundation & The AI Brain — ✅ [COMPLETED & VERIFIED]
- **Anthropic Claude 3.5 Haiku Client**: Integrated `claude-haiku-5-5` for high-precision, sub-second semantic ATS matching and fit percentage scoring.
- **Candidate Master Profile**: Structured `profile.json` storing verified skills, education, experience, and target roles.
- **Screening Question Solver**: Candidate fact recall and technical MCQ answering engine.

---

## Phase 2: Database & Web Dashboard — ✅ [COMPLETED & VERIFIED]
- **SQLAlchemy 2.0 ORM**: Structured database schema with ACID transactions (`jobs`, `applications`, `application_answers`).
- **FastAPI REST Server**: Modular API endpoints with CORS configuration and Pydantic validation.
- **Cyber-Precision Web Dashboard**: Modern React 19 + Vite Kanban board with search, filtering, and job inspection modals.

---

## Phase 3: Browser Automation & Naukri Job Discovery — ✅ [COMPLETED & VERIFIED]
- **Stealth Playwright Crawler**: Multi-page pagination on Naukri.com with anti-detection flags (`--disable-blink-features=AutomationControlled`).
- **Semantic Query Expansion**: `query_expander.py` dynamically expanding candidate titles into high-yield search terms.
- **Automated Ingestion Pipeline**: Deduplication and triage sorting jobs into *Ready to Apply* or *Filtered / Low Match*.

---

## Phase 4: Autonomous 1-Click Application Engine — ✅ [COMPLETED & VERIFIED]
- **Supreme Crawler Authority**: Real physical DOM buttons override JD text boilerplate to distinguish 1-Click Apply from External Links.
- **Tri-Engine Screening Chatbot Solver**: Resolves complex Naukri drawer questions combining candidate facts, Claude 3.5 Haiku, and human keystroke typing simulation (12–35ms).
- **Adaptive Fresher Salary Skip**: Autonomously skips, selects "Negotiable", or uses safe numeric fallbacks (`0`) for candidates with <1 year experience.
- **Post-Click Redirection Watchdog**: Detects external URLs and opens them cleanly in new tabs without stalling the apply loop.

---

## Phase 5: Recruiter Discovery, Outreach & Telemetry — ✅ [COMPLETED & VERIFIED]
- **Real-Time SSE EventBus**: `/api/events/stream` emitting live application progress and state transitions.
- **Stealth Engine & Timing Jitter**: Randomized Bézier mouse paths, typing jitter, and anti-detection headers.
- **Recruiter Outreach Console**: Automated Gmail SMTP cold email dispatch with tailored resume attachments.
- **Conversion Funnel Analytics**: Interactive KPI counters and pipeline velocity metrics.

---

## Phase 6: Enterprise Multi-Tenant SaaS & Docker Transformation — ✅ [100% COMPLETED & VERIFIED]

### Step 6.1: Multi-Tenant Schema & JWT Authentication (`test_phase1.py`)
- Created `users` table with bcrypt password hashing.
- Implemented `/api/auth/register`, `/api/auth/login`, and Bearer JWT auth dependency (`get_current_user`).
- Migrated `jobs`, `applications`, and `qa_bank` tables to enforce `user_id` foreign keys and tenant-scoped queries.

### Step 6.2: Per-User Storage Vaults & Session Isolation (`test_phase2_step1-4.py`)
- Built `backend/app/core/user_storage.py` provisioning isolated vaults at `data/users/{user_id}/`.
- Scoped Naukri mobile OTP authentication to candidate browser session vaults (`data/users/{uid}/browser_session/`).
- Verified Zero-Theft Resume Guard and independent tenant portal disconnect.

### Step 6.3: Concurrent Multi-Tenant Auto-Pilot & Task Queue (`test_phase3_step1-3.py`)
- Implemented `MultiTenantTaskQueue` (`backend/app/agent/task_queue.py`) with independent per-user `asyncio.Lock()` instances.
- Enabled simultaneous discovery and application runs across multiple candidates without server blocking.
- Implemented per-user daily quota tracking (`applied_today` per `user_id`) and Anti-Eavesdropping SSE telemetry guard.

### Step 6.4: Full Dockerization & DevOps Microservices Packaging (`test_phase4_step1-3.py`)
- Built multi-stage `Dockerfile.backend` (Python 3.12, Playwright Chromium, non-root user `appuser:1001`).
- Built multi-stage `Dockerfile.frontend` (Node 20 build + Nginx 1.27 Alpine production server).
- Configured Nginx reverse proxy (`frontend/nginx.conf`) with zero-buffering for SSE and client-side SPA routing.
- Orchestrated with `docker-compose.yml` (`shm_size: 2gb`, persistent volumes).
- Authored production launch scripts: `./start.sh` and `start.bat`.

### Step 6.5: Two-User Live End-to-End Simulation & Verification (`test_phase5_step1-3.py`)
- Provisioned User 1 (`Rayavaram Jayasurya`) and User 2 (`Candidate Two`) with unique JWT tokens and distinct ATS profiles.
- Verified dual Naukri browser session isolation and OTP anti-hijacking guard.
- Executed concurrent task queue runs with discrete skill matching and isolated proof snapshots.
- Verified independent quota enforcement (User 1 paused on quota exhaustion; User 2 continued).
- Verified surgical tenant cleanup with Master User Deletion Shield protecting User 1.

---

## Summary Checklist

| Phase | Milestone Description | Implementation Status | Test Suite Verification |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Anthropic Claude AI Brain & ATS Scorer | ✅ Completed | Tested & Verified |
| **Phase 2** | Database & Cyber-Precision React Dashboard | ✅ Completed | Tested & Verified |
| **Phase 3** | Naukri Multi-Page Stealth Crawler & Ingestion | ✅ Completed | Tested & Verified |
| **Phase 4** | 1-Click Apply & Tri-Engine Screening Solver | ✅ Completed | Tested & Verified |
| **Phase 5** | Recruiter Outreach, Stealth & Real-Time SSE | ✅ Completed | Tested & Verified |
| **Phase 6** | Multi-Tenant SaaS, Docker & Task Queue | ✅ Completed | `test_phase1` to `test_phase5` (100% Pass) |

---
*All 6 milestones are 100% completed, fully integrated, and verified in production.*
