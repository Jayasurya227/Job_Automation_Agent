# <span style="color: #2563EB;">LangGraph Workflow Guide: Autonomous Job Agent</span>

> **Overview**: This document explains what LangGraph is, how it works, and exactly how it is used as the orchestration engine in our Autonomous Job Automation Agent.

---

## <span style="color: #2563EB;">1. What is LangGraph?</span>

- **In Simple Words**: LangGraph is a framework that organizes an AI agent's work into a clear **State Machine (a step-by-step flowchart)**.
- **The Core Purpose**: Instead of writing long, messy Python `if/else` loops, LangGraph treats every action as a "station" on an assembly line.
- **Why It Matters**: It gives us complete control over what the AI does, prevents endless loops, and allows us to **pause the agent and wait for human approval**.

---

## <span style="color: #2563EB;">2. The 3 Core Building Blocks of LangGraph</span>

LangGraph operates using only 3 simple concepts:

### **1. The State (The Shared Clipboard)**
- A shared data container passed from worker to worker.
- It holds all current information about the job being processed:
  - `job_title`: e.g., *"Python Developer"*
  - `company`: e.g., *"Google"*
  - `job_description`: Full text of requirements
  - `match_score`: e.g., *88%*
  - `tailored_resume_pdf`: Path to the generated PDF
  - `human_approved`: `True` or `False`

### **2. The Nodes (The Workers)**
- Small, focused Python functions that perform **one specific task** and update the State:
  - **Scraper Node**: Uses Playwright to extract job details.
  - **Scorer Node**: Uses Gemini to analyze requirements and calculate match score.
  - **Resume Node**: Uses Gemini and LaTeX to compile a tailored PDF resume.
  - **Applier Node**: Uses Playwright to fill and submit the job application form.

### **3. The Edges (The Traffic Lights / Decision Rules)**
- The connections between nodes that decide what happens next:
  - **Normal Edge**: Moves directly from one step to the next (e.g., from Scraper ➔ Scorer).
  - **Conditional Edge**: Makes a smart decision based on rules (e.g., *Is the score >= 75%?* If YES, go to Resume Tailoring. If NO, go to Archive/Skip).

---

## <span style="color: #2563EB;">3. How LangGraph Works in OUR Project</span>

### Visual Agent Flow:

```
               ┌──────────────────────────────┐
               │    Start: Job Discovered     │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │     Node 1: SCORER NODE      │ (Gemini reads the JD)
               └──────────────┬───────────────┘
                              │
                              ▼
                 〈 Is Match Score >= 75%? 〉
                    /                    \
        (NO: Low Match)                (YES: High Match)
                  /                        \
                 ▼                          ▼
      ┌────────────────────┐     ┌──────────────────────────────┐
      │ Node: ARCHIVE NODE │     │  Node 2: TAILOR RESUME NODE  │ (Generates tailored PDF)
      │  (Skip & log to DB)│     └──────────────┬───────────────┘
      └────────────────────┘                    │
                                                ▼
                                 ┌──────────────────────────────┐
                                 │   ⏸️ HUMAN APPROVAL PAUSE    │ (LangGraph PAUSES here!)
                                 │   (Waits for user approval)  │
                                 └──────────────┬───────────────┘
                                                │ (User clicks "Approve" on Dashboard)
                                                ▼
                                 ┌──────────────────────────────┐
                                 │     Node 3: APPLIER NODE     │ (Playwright submits form)
                                 └──────────────┬───────────────┘
                                                │
                                                ▼
                                 ┌──────────────────────────────┐
                                 │     END: Logged in SQLite    │
                                 └──────────────────────────────┘
```

---

## <span style="color: #2563EB;">4. Real-World Scenarios Handled by LangGraph</span>

Here are the 4 specific real-world scenarios where LangGraph manages our application:

### **Scenario A: High-Match Job (Match Score >= 75%)**
- **Trigger**: Gemini scores a job at 88%.
- **LangGraph Action**: The conditional edge automatically routes the job to the **Resume Tailor Node**, generating a custom LaTeX PDF emphasizing the matching skills.

### **Scenario B: Low-Match Job (Match Score < 75%)**
- **Trigger**: Gemini scores a job at 40% (e.g., missing critical requirements).
- **LangGraph Action**: The conditional edge automatically routes the job to the **Archive Node**. It logs the job in SQLite as *"Skipped"* so we never waste applications on irrelevant roles.

### **Scenario C: Human-in-the-Loop Approval (Assisted Mode)**
- **Trigger**: The tailored resume is ready, and the application form is filled.
- **LangGraph Action**: LangGraph triggers a native **`interrupt()`**. 
  - The agent freezes execution safely.
  - The dashboard notifies the candidate: *"Google application ready. Review & Approve?"*
  - When the candidate clicks **"Approve"**, LangGraph resumes from the exact checkpoint and submits the application.

### **Scenario D: Network Crash or Interruption Recovery**
- **Trigger**: Wi-Fi drops or your laptop restarts in the middle of an application.
- **LangGraph Action**: LangGraph uses **SQLite Checkpointing**. 
  - It saves the exact state of every node to local storage.
  - When the app restarts, it does not re-run previous steps; it resumes exactly from the last saved node.

---

## <span style="color: #2563EB;">5. Why We Chose LangGraph (Key Advantages)</span>

- **Built-in Human Approval**: No need to write complex custom pause/resume code; LangGraph handles interrupts natively.
- **Zero Confusion / High Visibility**: The workflow can be visualized as an actual graph diagram on your dashboard.
- **Clean Architecture**: Separates the reasoning logic from browser actions, making debugging fast and simple.
- **Industry Standard**: Demonstrates modern, cutting-edge agentic design to hiring managers and recruiters.

---
