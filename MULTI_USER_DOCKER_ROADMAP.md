# 🚀 Multi-User & Docker Production SaaS Roadmap
**Project:** Autonomous AI Job Application Agent  
**Author:** Rayavaram Jayasurya & Antigravity AI  
**Created:** 2026-11-09  
**Status:** Saved & Approved Blueprint (Pending Execution)

---

## 📌 Executive Summary & Vision
This roadmap outlines the complete transformation of the Job Automation Agent from a local single-user developer tool into an **Enterprise-Grade Multi-User SaaS Platform**. 

The goal is to enable **multiple concurrent candidates (5 to 10+ users)** to register, upload their distinct resumes, configure custom job preferences, authenticate their individual job portal accounts (Naukri, Indeed) via mobile OTP, and run autonomous job applications simultaneously without data collisions, cross-user cookie leakage, or server freezes.

---

## 🏛️ Current State vs. Future Multi-User SaaS Architecture

| Component | Current State (Single-User) | Future State (Multi-User SaaS) |
| :--- | :--- | :--- |
| **Authentication** | Single hardcoded profile (`Jayasurya Rayavaram`) | Secure JWT auth with password hashing (`bcrypt`), Sign Up / Sign In screens |
| **User Data Isolation** | Global `profile.json`, single `uploaded_resume.pdf` | Isolated directory per user: `data/users/{user_id}/profile.json`, `resume.pdf` |
| **Portal Sessions** | Global `browser_session/` folder for 1 Naukri account | User-specific session vaults: `data/users/{user_id}/browser_session/` |
| **Database** | SQLite with single unmapped `jobs` & `applications` | Multi-tenant schema with `user_id` foreign keys (PostgreSQL / SQLite multi-tenant) |
| **Auto-Pilot Scheduler** | Single-threaded sequential discovery & apply | Distributed background queue (Celery + Redis) processing multi-user jobs concurrently |
| **Deployment & Ops** | Local terminal scripts on Windows host | Containerized microservices via **Docker** and **Docker Compose** (`docker-compose up -d`) |

---

## 🛡️ What We Keep (100% Preserved - Zero Waste)
The core job application automation engine has been battle-tested and perfected with **Zero Remarks**. We do **NOT** rewrite or discard:
1. **Supreme Crawler Authority (`scraper.py` & `ingestion.py`):** Real physical DOM button overrides JD text boilerplate.
2. **Post-Click Redirection Watchdog (`applier.py`):** 3-case guard detecting external URL navigation, popup tabs, and redirect modals.
3. **Tri-Engine Chatbot Solver (`qa_bank.py` & `applier.py`):** Profile Facts + Claude Haiku Technical MCQs + Human keystroke typing simulation (12-35ms).
4. **Interactive Dashboard UI (`frontend/src/`):** Kanban board, Table view, Timetable micro-pill, Profile editor, and Settings tab layouts.

---

## 📋 The 5-Phase Implementation Master Plan

### 🔹 Phase 1: Real Multi-User Authentication & Database Isolation
* **Users Table:** Add `users` table (`id`, `email`, `password_hash`, `full_name`, `created_at`, `is_active`).
* **Security & Tokens:** Implement JWT token generation, refresh tokens, and password hashing using `passlib[bcrypt]`.
* **Frontend Authentication:** Build modern, responsive Sign Up, Sign In, and Logout flows in React.
* **Schema Migration:** Add `user_id` foreign key to `jobs`, `applications`, and `qa_bank` tables so every query is strictly filtered by `current_user.id`.

### 🔹 Phase 2: Per-User Storage & Portal Session Isolation
* **User Storage Vaults:** Standardize per-user directory structure:
  ```text
  backend/data/users/{user_id}/
  ├── profile.json            # Candidate personal info, preferences, skills
  ├── uploaded_resume.pdf     # Master PDF resume
  ├── tailored_resumes/       # Generated tailored LaTeX / PDFs
  ├── browser_session/        # Chromium user data & active Naukri session cookies
  └── output/snapshots/       # Proof screenshots for candidate review
  ```
* **Independent Portal Connections:** When User B connects their Naukri account via Mobile OTP:
  - OTP and browser session are scoped exclusively to `data/users/{user_2_id}/browser_session/`.
  - User A's session remains untouched and safe.

### 🔹 Phase 3: Concurrent Multi-Tenant Auto-Pilot & Task Queue
* **Task Queue Architecture:** Integrate **Redis** and **Celery** (or FastAPI background thread pools) for async processing.
* **Independent Timetables:** Each user gets their own 9:00 AM – 9:00 PM IST timetable cadence and daily quota counter (`applied_today` per `user_id`).
* **Concurrent Workers:** Worker A processes User 1's applications while Worker B handles User 2's discovery, preventing server latency or timeouts.

### 🔹 Phase 4: Full Dockerization & DevOps Packaging
* **`Dockerfile.backend`:** Container with Python 3.11, FastAPI, Playwright, and Chromium system dependencies.
* **`Dockerfile.frontend`:** Multi-stage build with Node.js and Nginx alpine reverse proxy for production static serving.
* **`docker-compose.yml`:** Single configuration managing `backend`, `frontend`, `db` (PostgreSQL), and `redis` services.
* **Portability Guarantee:** One single terminal command to launch the entire multi-user platform on any OS or cloud VM (AWS EC2, GCP Compute Engine, DigitalOcean Droplet):
  ```bash
  docker-compose up -d --build
  ```

### 🔹 Phase 5: Two-User Live End-to-End Simulation & Verification
* **Test Setup:**
  - Create **User 1 (Jayasurya Rayavaram)** with master AI Engineer profile.
  - Create **User 2 (Test Candidate / Friend)** with distinct profile and resume.
* **Verification Checks:**
  1. User 1 logs in -> sees only User 1's jobs and history.
  2. User 2 logs in -> sees only User 2's jobs and history (100% data privacy).
  3. User 1 connects Naukri -> User 2 connects Naukri -> Both sessions remain separate and active.
  4. Auto-Pilot triggers for both users -> Proof screenshots captured and stored in respective user directories.

---

## 🎯 Final Milestone
Upon completing this roadmap, the platform transitions from an individual automation script into a **commercial-grade, cloud-deployable Multi-User AI Job Application SaaS platform**.

