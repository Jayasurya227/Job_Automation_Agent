# Project Master Guide: Autonomous Job Automation Agent (Multi-User SaaS)

---

## 1. Problem Statement

### The Real-World Challenge:
Job hunting in today's tech ecosystem is notoriously repetitive, mentally exhausting, and inefficient for candidates:
1. **Time Sink**: Searching across portals like Naukri takes hours of manual filtering, clicking, and reading repetitive job listings every day.
2. **Resume Tailoring Fatigue**: Applicant Tracking Systems (ATS) filter out candidates whose resumes lack exact keyword alignment. Manually tailoring resumes for 20+ jobs daily is unsustainable.
3. **Application Tracking Chaos**: Candidates struggle to track which roles they applied to, which resume was submitted, and where follow-ups are needed.
4. **Complex Screening Chatbots**: Portals like Naukri frequently intercept 1-click applies with multi-step screening drawers asking notice period, location, salary, and technical MCQs. Freshers often get stuck on required past salary fields.
5. **Multi-User Collaboration & Privacy**: Multiple job seekers (colleagues, friends, or family) often need autonomous assistance, but legacy automation scripts rely on global hardcoded configurations, causing session hijacking, cookie collisions, and resume cross-contamination.

### The Solution:
An **Enterprise-Grade Multi-User AI Job Application SaaS Platform (Dockerized)** that functions as an autonomous career command center: discovering high-match jobs on Naukri.com, scoring ATS alignment with Anthropic Claude, intelligently solving screening questionnaires (with dynamic fresher salary skip), managing persistent browser sessions in isolated user vaults, and running concurrent pipelines in Docker with complete tenant privacy.

---

## 2. Comprehensive Project Research & Engine Selection

### Market & Competitive Landscape:
- Tools like *Simplify.jobs*, *Teal*, and *LazyApply* demonstrate massive demand.
- **Where existing tools fail**: They often get accounts banned by spamming high volumes without humanized delays, crash on complex dynamic screening drawers, or operate as single-user client extensions that leak candidate data.

### Technical Feasibility & Reality Check:
1. **Anti-Bot Defenses & Portal Safety (Naukri.com)**:
   - *Our Strategy*: Use **Per-User Persistent Browser Vaults** (`data/users/{uid}/browser_session/`) + **Humanized Jitter** (15ms–45ms typing delays, 1.5s–3.5s page pauses) + **Configurable Daily Quotas** (default 25 applications/day).
2. **LLM Intelligence for ATS Optimization**:
   - Powered by **Anthropic Claude 3.5 Haiku (`claude-haiku-5-5`)** for sub-second, zero-hallucination semantic matching, fit percentage calculation, and automated screening question resolution.
3. **Multi-Tenant SaaS Data Isolation**:
   - Every candidate has their own cryptographically signed JWT token, row-level database isolation (`WHERE user_id = current_user.id`), and physical storage vault (`data/users/{user_id}/`) protecting resumes, cookies, and proof snapshots.
4. **Production DevOps & Portability**:
   - Microservices architecture containerized with **Docker** and **Docker Compose**, orchestrated via an **Nginx** reverse proxy with zero-buffering for Server-Sent Events (SSE) and 2GB shared memory for Playwright Chromium stability.

---

## 3. System Architecture

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

## 4. Pre-Requirements & Technology Stack

### 1. Core Stack:
- **Python 3.12+**: High-performance backend runtime powering FastAPI and Playwright.
- **Node.js 20+ & Vite**: Next-generation frontend build tooling and React 19 environment.
- **Docker & Docker Compose**: Unified microservices containerization.
- **Nginx 1.27 Alpine**: High-efficiency production web server and reverse proxy.
- **Playwright (Chromium)**: Modern stealth browser automation engine.
- **Dual-Engine Database**: SQLAlchemy 2.0 ORM supporting embedded SQLite (WAL mode, foreign keys) or Cloud PostgreSQL.

### 2. Security & Credentials:
- **Anthropic Claude API Key**: Obtained from [Anthropic Console](https://console.anthropic.com/).
- **JWT Secret Key**: Cryptographically random 256-bit string for signing auth tokens.
- **Naukri.com Account**: Candidate credentials with mobile OTP authentication.

### 3. Tenant Data Assets:
- Master PDF Resume (`uploaded_resume.pdf`) uploaded via UI into `data/users/{uid}/`.
- Candidate profile facts (`profile.json`) configuring target roles, skills, and ATS thresholds.

---

## 5. Implementation Roadmap & Architecture Milestones

The platform was built following rigorous phase-by-phase engineering:

* **Phase 1: Foundation & The AI Brain (Anthropic Claude 3.5)**:
  Implemented Claude 3.5 Haiku client wrapper, semantic ATS scoring engine, weighted skill gap analysis, and screening questionnaire solver.
* **Phase 2: Database & Cyber-Precision Web Dashboard (React 19)**:
  Built SQLAlchemy models, ACID transaction management, FastAPI REST endpoints, and modern Kanban board UI with live status indicators and job inspection modals.
* **Phase 3: Browser Automation & Naukri Job Discovery**:
  Developed multi-page stealth crawler for Naukri.com with semantic query expansion, anti-bot flags, and deduplication triage.
* **Phase 4: Autonomous 1-Click Application & Tri-Engine Screening Solver**:
  Engineered Playwright 1-Click application executor, post-click redirection watchdog, and tri-engine chatbot solver with adaptive fresher salary skip.
* **Phase 5: Recruiter Discovery, Outreach & Real-Time Telemetry**:
  Built real-time SSE EventBus, automated Gmail SMTP cold outreach engine, and interactive funnel analytics.
* **Phase 6: Multi-Tenant SaaS Transformation & Full Dockerization**:
  Implemented cryptographic JWT authentication, per-user isolated storage vaults (`data/users/{uid}/`), `MultiTenantTaskQueue` concurrency with per-user locks, Zero-Theft Resume Guard, Anti-Hijacking OTP Guard, Master User Deletion Shield, Docker microservices packaging, and Nginx reverse proxy. Verified with comprehensive end-to-end multi-user test suites.

---

## 6. Core Engineering Rules & Tenets

1. **Strict Tenant Data Isolation**:
   No candidate can ever access, view, or modify another candidate's jobs, applications, resumes, browser cookies, or telemetry logs.
2. **Supreme Crawler Authority**:
   Real physical DOM button interactions always take precedence over static job description boilerplate text.
3. **Fail-Safe Redirection Watchdog**:
   External redirects and company portal links are cleanly classified and opened in new tabs, preventing broken automated apply loops.
4. **Adaptive Fresher Protection**:
   Candidates with fresher experience levels (<1 year) are never stalled by required past salary fields; the agent autonomously skips or selects safe fallbacks.
5. **Production Docker Portability**:
   The entire full-stack platform must spin up reliably with a single terminal command (`docker compose up -d --build` or `./start.sh` / `start.bat`) on any operating system or cloud virtual machine.

---

*Reference this guide for high-level system comprehension, architectural rationale, and production deployment standards.*
