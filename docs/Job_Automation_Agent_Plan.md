# Job Automation Agent Plan: Enterprise Multi-User Platform

---

## 1. Overview & Vision
The **Autonomous Job Automation Agent** is an enterprise-grade, multi-user AI platform designed to automate the entire job discovery, ATS evaluation, screening questionnaire resolution, and application submission process on behalf of multiple concurrent job seekers.

### Candidate Inputs (Per-User Storage Vault)
Each candidate registers an account and provides:
- **Master PDF Resume**: Uploaded securely to their isolated vault (`data/users/{uid}/uploaded_resume.pdf`).
- **Candidate Preferences (`profile.json`)**:
  - Target job titles (e.g., *AI Engineer*, *Full Stack Developer*, *Python Developer*)
  - Preferred locations (e.g., *Hyderabad*, *Bengaluru*, *Remote*)
  - Experience level & verified candidate facts (notice period, current CTC, education)
  - Work mode preferences (Remote / Hybrid / Onsite)
  - ATS Match Thresholds (Ready threshold: 70%, Auto-apply threshold: 75%)

---

## 2. Multi-Tenant Architecture & Data Isolation

```
Candidate A ──► JWT Auth ──► Vault A (data/users/1/) ──► Naukri Session A ──► Concurrent Task
Candidate B ──► JWT Auth ──► Vault B (data/users/2/) ──► Naukri Session B ──► Worker Pool
```

- **Row-Level Tenant Security**: Every database query filters by `user_id = current_user.id`.
- **Zero-Theft Storage Vaults**: Resumes, profile data, and proof screenshots are isolated per user.
- **Anti-Hijacking OTP Guard**: Naukri.com sessions and cookies are saved in candidate-specific directories, preventing session crosstalk.
- **Concurrent Task Queue**: The `MultiTenantTaskQueue` processes tasks using independent per-user `asyncio.Lock()` instances.

---

## 3. Core Automation Workflow: Naukri.com

### Step 1: Stealth Multi-Page Job Discovery
1. **Target Portal**: **Naukri.com** (primary battle-tested portal with deep Indian and international tech listings).
2. **Stealth Crawler**:
   - Launches Chromium with `--disable-blink-features=AutomationControlled` and persistent session cookies.
   - Executes semantic query expansion (`query_expander.py`) across target titles.
   - Paginates through search results, extracting Job Title, Company, Experience, Location, and JD text.
   - Performs automated deduplication against the candidate's existing database history.

### Step 2: Zero-Hallucination ATS Scoring (Anthropic Claude 3.5 Haiku)
1. Evaluates target JDs against the candidate's master profile.
2. Computes weighted match score (0–100%) based on:
   - Required & good-to-have technical skills
   - Experience alignment
   - Domain relevance and educational prerequisites
3. Categorizes jobs into:
   - **Ready to Apply** ($\ge 75\%$ match)
   - **Filtered / Low Match** ($< 70\%$ match)

### Step 3: Autonomous 1-Click Application & Screening Chatbot Solver
1. **Supreme Crawler Authority**: Real DOM buttons determine application type (1-Click Apply vs External Link).
2. **Tri-Engine Screening Chatbot Solver**:
   - *Layer 1 (Candidate Facts):* Immediate lookup of notice period, location, and verified experience.
   - *Layer 2 (Adaptive Fresher Salary Skip):* Detects fresher experience (<1 year) and autonomously clicks "Skip", selects "Not Disclosed / Negotiable", or injects safe numeric fallbacks (`0`).
   - *Layer 3 (Claude Haiku Bridge):* Fast inference for dynamic technical MCQs and recruiter screening questions.
3. **Proof Capture**: Automatically records visual proof snapshots (`data/users/{uid}/output/snapshots/`) upon successful submission.

### Step 4: Anti-Ban Quota & Timetable Enforcement
- Enforces daily application limits (default 25/day, customizable per user).
- Operates within an autonomous timetable cadence (e.g., 9:00 AM – 9:00 PM IST) with humanized typing jitter (15ms–45ms) and randomized action delays.

---

## 4. Recruiter Outreach & Cold Email Engine

1. **Recruiter Discovery**:
   - Identifies hiring managers and talent acquisition contacts associated with target roles.
2. **Personalized Cold Email Generation**:
   - Drafts concise, natural, 75-word emails referencing specific candidate accomplishments and target role requirements.
3. **Automated Sending via Gmail SMTP**:
   - Uses secure Google App Passwords to dispatch emails with tailored resumes attached, enforcing a safe daily sending limit (5–10 emails/day).

---

## 5. Deployment & Infrastructure

- **Containerized Microservices**: Orchestrated via Docker Compose with dedicated backend (Python 3.12 + Playwright) and frontend (React 19 + Nginx) containers.
- **Nginx Reverse Proxy**: Unified entry point on port 5173 with SSE zero-buffering support.
- **Dual-Engine DB Support**: Multi-tenant SQLite with WAL mode enabled out-of-the-box, or Cloud PostgreSQL via `DATABASE_URL`.
- **One-Command Startup**: Launchable via `./start.sh` or `start.bat`.

---
*This document defines the high-level operational blueprint and technical workflow for the multi-user platform.*
