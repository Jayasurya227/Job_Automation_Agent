# Job Automation Agent Plan

## Overview & Problem Statement
**Autonomous Job Automation Agent**

The proposed system is an autonomous job automation agent that can manage most of the job search and application process on behalf of a candidate.

### Candidate Inputs
The candidate provides:
- **Master Resume**
- **Basic Preferences**:
  - Up to 3 target job titles
  - Preferred locations
  - Experience level
  - Salary expectations
  - Work preferences (Remote / Hybrid / Onsite)

The agent then searches for suitable jobs, customizes applications, communicates with recruiters, tracks responses, and continuously improves its approach based on previous results.

---

## Step-by-Step Workflow & Core Capabilities

### Step 1: Automated Job Search, Resume Customization and Job Applications

1. **Job Search across Multiple Portals**:
   - The system automatically searches for the latest relevant jobs across major job portals:
     - LinkedIn
     - Naukri
     - Indeed
     - Glassdoor
     - Foundit
     - Wellfound
     - Internshala
     - Cutshort
     - Instahyre
     - Hirist
     - Shine
     - TimesJobs
     - Company career portals and other supported job platforms.
   - The agent identifies jobs based on the candidate's selected job titles and profile.

2. **Job Description (JD) Analysis & Relevance Scoring**:
   - For every job, it analyzes the Job Description against the Master Resume.
   - Determines the relevance of the opportunity based on:
     - Skills
     - Experience
     - Job title
     - Technologies
     - Education
     - Projects
     - Location
     - Work mode
     - Other specific job requirements.

3. **ATS-Friendly Resume Customization (LaTeX & Overleaf)**:
   - For relevant jobs, the agent automatically creates a job-specific ATS-friendly resume.
   - The resume is generated using Overleaf and LaTeX.
   - Relevant skills, experience, projects, and keywords are emphasized according to the Job Description.

4. **Application Submission & Form Answering**:
   - The system uses the customized resume to complete the application process.
   - If the application contains questions, the agent answers them using the candidate's verified profile and Master Resume.
   - For uncertain or sensitive questions, the agent requests user confirmation rather than making up information.

5. **Portal Permissions & Application History**:
   - The system maintains permissions for each job portal so the candidate controls which platforms the agent is allowed to access and apply through.
   - A complete history of every application is maintained, including:
     - Job title
     - Company
     - Portal
     - Resume version used
     - Application date
     - Application status
     - Questions answered
     - Application result.

---

### Step 2: HR Contact Discovery and Automated Cold Email Outreach

1. **Recruiter & HR Contact Discovery**:
   - The agent searches publicly available sources to identify relevant:
     - HR professionals
     - Recruiters
     - Talent acquisition specialists
     - Hiring managers
     - Recruitment contacts.
   - The system connects these contacts with relevant companies and job opportunities.

2. **Personalized Cold Email Generation**:
   - For suitable opportunities, the agent automatically creates a personalized cold email containing:
     - Short personalized introduction
     - Relevant candidate experience
     - Reason for contacting the recruiter
     - Job or role reference
     - Customized ATS-friendly resume
     - Job-specific cover letter
     - Relevant portfolio or professional links.
   - The email is written to be natural, concise, personalized, and human-like rather than looking like a generic generated template.

3. **Outreach Tracking & Automated Follow-Ups**:
   - The system tracks:
     - Emails sent
     - Delivery status
     - Replies
     - Positive responses
     - Negative responses
     - Follow-ups
     - No-response cases.
   - The agent optionally sends follow-up emails when no response is received within a configured period.

---

### Step 3: Self-Learning and Continuous Improvement

1. **Analysis of Past Outcomes**:
   - The system analyzes historical data:
     - Job applications submitted
     - Customized resumes used
     - Cover letters sent
     - Cold emails sent
     - Recruiter responses
     - Rejections
     - Interview invitations
     - Screening results
     - No-response cases.

2. **Continuous Strategy Optimization**:
   - Based on these results, the agent continuously improves future applications by identifying:
     - Which resume formats perform better
     - Which skills and keywords are frequently relevant
     - Which email formats receive more responses
     - Which subject lines generate better engagement
     - Which cover-letter structures work better
     - Which application questions frequently appear
     - Which answers are appropriate for recurring questions
     - Which types of jobs generate more positive responses.

3. **Candidate Knowledge Base & Truth Preservation**:
   - The agent uses this information to improve future resumes, cover letters, emails, and application answers **without changing factual information about the candidate**.
   - Maintains a **Candidate Knowledge Base** containing verified information that can be safely reused when answering application questions.
   - For uncertain or sensitive questions, the agent requests user confirmation rather than making up information.

---

### Step 4: Job Search Dashboard, Analytics and Activity Tracking

1. **Centralized Monitoring Dashboard**:
   - Centralized dashboard where the candidate monitors the entire job-search process.

2. **Job Statistics**:
   - Total jobs discovered
   - Relevant jobs
   - Jobs applied to
   - Jobs by portal
   - Jobs by company
   - Jobs by job title
   - Jobs applied today, this week, and this month.

3. **Application Statistics**:
   - Applications submitted
   - Applications in progress
   - Applications viewed
   - Recruiter responses
   - Interview invitations
   - Rejections
   - No-response applications
   - Offers.

4. **Email and Outreach Statistics**:
   - HR contacts discovered
   - Emails sent
   - Emails replied to
   - Positive responses
   - Negative responses
   - Follow-ups sent
   - Pending follow-ups.

5. **AI Email Categorization**:
   - Analyzes received emails and categorizes them into meaningful groups:
     - Positive
     - Negative
     - Neutral
     - Interview opportunity
     - Rejection
     - Follow-up required
     - Action required.

6. **Activity Timeline (Live Event Stream)**:
   - Typical end-to-end activity cycle:
     1. **Job Found**
     2. **Job Analyzed**
     3. **Resume Customized**
     4. **Application Submitted**
     5. **HR Contact Found**
     6. **Cold Email Sent**
     7. **Recruiter Response Received**
     8. **Response Analyzed**
     9. **Interview, Rejection, or Follow-up**
   - Allows the candidate to understand exactly what happened during the day and what actions require attention.

---

## Step 5: Controls, Safeguards and Governance

1. **Human Approval Controls (3 Operating Modes)**:
   - **Fully Autonomous Mode**: The agent performs approved actions automatically.
   - **Approval Mode**: The agent prepares applications and emails but asks for approval before sending or submitting them.
   - **Assisted Mode**: The agent performs research and preparation while the candidate performs the final submission.

2. **Duplicate Prevention**:
   - Detects when the same job appears on multiple portals and prevents duplicate applications.

3. **Application Limits & Preferences**:
   - Configurable limits:
     - Maximum applications per day
     - Maximum applications per portal
     - Preferred locations
     - Minimum salary
     - Allowed job types
     - Preferred experience level.

4. **Security and Audit Trail**:
   - Every important action is recorded (job interacted with, resume used, email sent, questions answered, timestamp, result).
   - Sensitive credentials and personal information are securely stored and protected.

---

## Overall Objective
To build a persistent autonomous career agent that manages the complete job-search workflow:
- Finding jobs
- Analyzing jobs
- Customizing resumes
- Applying to jobs
- Finding recruiters
- Sending personalized emails
- Tracking responses
- Analyzing results
- Learning from previous outcomes
- Improving future applications

Instead of the candidate manually repeating these activities across multiple platforms, the agent continuously handles the repetitive work while keeping the candidate in control of important decisions and providing complete visibility through the dashboard.
