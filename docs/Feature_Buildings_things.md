# Feature Building & Future Enhancements Backlog

> **Purpose**: A centralized product backlog to capture high-value features, optimizations, and upgrades identified during each phase of development, ready to be implemented in future iterations.

---

## First Phase: Enhancements & Upgrades

The following three high-value features were identified during **Phase 1 (The AI Brain)** to take the system from production-grade to elite enterprise level:

### 1. Persistent Database History & Job Tracking (SQLite Integration) — ✅ [COMPLETED IN PHASE 2]
- **Status**: Implemented with SQLite ACID transactions, FastAPI REST endpoints, and Web Dashboard Kanban board.
- **Value**:
  - Automatically records every job analyzed, company name, match score, tailored resume path, and application timestamp.
  - Historical analytics on the dashboard (Tracked jobs, Average ATS score, Ready to apply, Applied).
  - Eliminates duplicate applications.

---

### 2. Multi-Template LaTeX Variety (Style Selector)
- **Concept**: Offer multiple ATS-compliant resume visual designs instead of a single template.
- **Value**:
  - **Template 1: Modern Tech / AI Engineer** (Our current single-column, clean charter font style).
  - **Template 2: Executive Classic** (Traditional serif layout, ideal for established enterprises and MNCs).
  - **Template 3: Compact Startup Minimalist** (Dense, high-information layout for fast-moving startups).
  - Allows candidates to select their favorite visual aesthetic with 1 click on the Dashboard.
- **Target Implementation**: Phase 4 Polish.

---

### 3. Built-in Zero-Install PDF Renderer (Non-LaTeX Machine Fallback)
- **Concept**: A built-in HTML/CSS-to-PDF rendering engine (using WeasyPrint or Playwright headless print) running alongside LaTeX.
- **Value**:
  - While LaTeX produces the cleanest ATS parsing, some candidate machines do not have `pdflatex` or MiKTeX installed.
  - Guarantees instant downloadable `.pdf` on any machine with zero external software installations.
- **Target Implementation**: Phase 4 Packaging.

---

## Second Phase Research: High-Value Upgrades from GitHub Analysis

Identified from deep architectural research comparing **AIHawk** and **JobSpy** against our system:

### 4. Multi-Portal Job Aggregator (`JobSpy` Integration)
- **Target Phase**: **Phase 3 (Browser Automation & Job Discovery)**
- **Concept**: Integrate `python-jobspy` to simultaneously discover jobs across **LinkedIn, Indeed, Naukri, Glassdoor, and ZipRecruiter**.
- **Value**:
  - Fetches hundreds of live job postings in seconds without requiring heavy browser rendering.
  - Native support for the Indian tech market via **Naukri** + global tech market via **LinkedIn / Indeed**.
  - Feeds directly into our `POST /api/analyze` pipeline and SQLite database.

### 5. Screening Question Memory Bank (Autonomous Q&A Auto-Filler)
- **Target Phase**: **Phase 4 (Autonomous Application Submission)**
- **Concept**: Connect the SQLite `application_answers` table to the Playwright form filler.
- **Value**:
  - Pre-records candidate-verified answers to common screening questions:
    - *"How many years of Python experience do you have?"*
    - *"What is your expected CTC / notice period?"*
    - *"Are you authorized to work in India / US?"*
  - When Playwright encounters an Easy Apply questionnaire, it looks up the verified answer from SQLite and fills it autonomously.

### 6. Anti-Detection Stealth Pacing & Persistent Sessions
- **Target Phase**: **Phase 3 & 4 (Scraper & Form Submitter)**
- **Concept**: Human-like randomized jitter delays (2.5s - 6.5s), natural page scrolling, and persistent Chromium user profiles.
- **Value**:
  - Ensures 100% account safety on LinkedIn and Indeed.
  - Eliminates CAPTCHA triggers and prevents automated bot detection bans that plague amateur GitHub scripts.

### 7. One-Click "Discover Jobs Now" Trigger on Web Dashboard
- **Target Phase**: **Phase 3 Dashboard Integration**
- **Concept**: Add a dedicated button on the Frontend Dashboard to launch the scraper asynchronously.
- **Value**:
  - User clicks "Discover Jobs" $\rightarrow$ Agent scrapes target roles from Master Profile $\rightarrow$ Evaluates match scores $\rightarrow$ New high-match cards appear on the Kanban board in real time.

---
*This backlog is actively tracked and will be reviewed as we enter each corresponding phase.*
