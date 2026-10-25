# <span style="color: #2563EB;">Project Prerequisites & Requirements</span>

> A simple, clear guide explaining every technology, tool, and framework used in this project, and the exact reason why we use it.

---

## <span style="color: #2563EB;">1. Tech Stack</span>

### **Python (v3.10+)**
- **What it is**: The main programming language for the backend.
- **Why we use it**: It is the industry standard for AI and automation. It runs our agent workflows, handles data, and connects the frontend to the AI.

### **SQLite**
- **What it is**: A lightweight, built-in database that runs inside a single file.
- **Why we use it**: It permanently remembers all applied jobs, interview calls, and tailored resumes so the agent never applies to the same job twice. It requires zero setup and costs $0.

### **LaTeX (pdflatex)**
- **What it is**: A professional document typesetting system.
- **Why we use it**: Standard Word documents often break ATS (Applicant Tracking System) scanners. LaTeX generates pixel-perfect, 100% ATS-friendly PDF resumes.

### **HTML, CSS, JavaScript (React / Vite)**
- **What it is**: The frontend technologies for the user interface.
- **Why we use it**: Creates a modern, responsive dashboard that works smoothly on both mobile phones and laptops to review matches and track applications.

---

## <span style="color: #2563EB;">2. Tools & Utilities</span>

### **Google AI Studio**
- **What it is**: Google's developer console for Gemini AI.
- **Why we use it**: Provides a 100% free API key giving us up to 1,500 free requests per day to power our AI Brain without paying any money.

### **VS Code / Antigravity IDE**
- **What it is**: The code editor and development environment.
- **Why we use it**: For writing, debugging, and managing our Python, Frontend, and LaTeX files.

### **Git & GitHub**
- **What it is**: Version control and code repository.
- **Why we use it**: Tracks all code changes, protects against mistakes, and hosts the project to showcase to recruiters and managers.

### **Gmail App Password (SMTP)**
- **What it is**: A secure 16-character password created inside your Google account.
- **Why we use it**: Allows Python to send personalized cold emails directly from your Gmail account to recruiters with your resume attached.

---

## <span style="color: #2563EB;">3. Agent Frameworks & Automation</span>

### **Playwright (Chromium)**
- **What it is**: A modern, high-speed browser automation framework.
- **Why we use it**: It acts as the "hands and eyes" of our agent. It automatically opens job portals (like LinkedIn and Indeed), searches for roles, extracts job descriptions, and auto-fills application forms.

### **Google Generative AI SDK (`google-generativeai`)**
- **What it is**: The official Python client library for Gemini.
- **Why we use it**: It acts as the "brain" of our agent. It reads the job description, compares it against your master profile, calculates match scores, and tailors resume bullet points.

### **Pydantic**
- **What it is**: A data validation and settings management library.
- **Why we use it**: Ensures that data coming from the AI or user forms is 100% accurate, strictly formatted, and free of missing fields.

### **LangGraph**
- **What it is**: An advanced state-machine framework for orchestrating multi-step AI agents.
- **Why we use it**: It acts as the workflow manager connecting all steps. Crucially, it provides native "Human-in-the-Loop" interrupts to pause the agent and wait for user approval before submitting applications.

### **Python-Dotenv (`python-dotenv`)**
- **What it is**: A security utility that loads environment variables from a `.env` file.
- **Why we use it**: Keeps your private Gemini API key and email passwords safe so they are never exposed in your public code.

---

## <span style="color: #2563EB;">4. Candidate Master Assets</span>

### **Master Profile (`profile.json`)**
- **What it is**: A single JSON file storing your verified personal facts (skills, projects, education, phone, links).
- **Why we use it**: It is the single source of truth. The agent reads this file to answer job application questions accurately without making up fake information.

### **Master Resume Template (`resume.tex`)**
- **What it is**: A clean, ATS-compliant LaTeX resume template.
- **Why we use it**: Serves as the base resume that the AI updates with matching keywords for every specific job.

---
