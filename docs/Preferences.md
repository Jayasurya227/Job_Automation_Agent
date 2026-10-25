# Preferences

## 1. Production-Grade & Multi-User Architecture
- **Target Standard**: The final application must not be a simple hobby project or a hardcoded single-user script. It must be engineered to a **production-ready, SaaS-grade standard**.
- **Multi-User Readiness**: The system architecture must be designed to support other users—allowing different job seekers to onboard, input their own master profiles, set personal preferences, and run the automation independently.
- **Enterprise-Level Reliability**: High emphasis on clean modular architecture, secure user data separation (privacy/security), robust error handling, and an intuitive, professional user interface that any candidate can use without technical knowledge.

## 2. Fully Responsive UI (Mobile & Laptop Support)
- **Dual-Device Optimization**: The user interface must work seamlessly on both mobile phones and laptops/desktops without broken layouts or cut-off text.
- **Mobile-Friendly**: Users opening links on smartphones can easily paste job descriptions, check match scores, and download tailored resumes with touch controls.
- **Desktop Experience**: Laptops and PCs get an expanded layout with side-by-side job matching, live resume previews, and full application tracking.

## 3. Human-in-the-Loop Control (LangGraph Orchestration)
- **Controlled State Machine**: The agent must operate as a reliable state graph using LangGraph rather than unpredictable free-roaming scripts.
- **Mandatory Approval Checkpoint**: The system must provide a built-in pause before the final application submission, allowing the candidate to review and approve the tailored resume on the dashboard.

## 4. Full Profile & Preferences Management (Edit & Update Anytime)
- **Dynamic Profile Editing**: Users can edit, update, or fix any detail (phone, target job titles, expected salary, notice period, work mode) anytime directly from the dashboard.
- **Resume Re-upload & Versioning**: Candidates can upload an updated Master Resume whenever they learn new skills or complete new projects, and the agent immediately uses the new version for future applications.

