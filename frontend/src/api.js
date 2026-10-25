/**
 * Autonomous Job Automation Agent - Central API Client
 * Connects Frontend directly to FastAPI Backend endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
      // fallback to status text
      errorDetail = response.statusText || errorDetail;
    }
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  // Health
  checkHealth: () => request('/api/health'),

  // Pipeline Metrics & Comprehensive Analytics
  getMetrics: () => request('/api/metrics'),
  getAnalytics: () => request('/api/analytics'),

  // Jobs
  getJobs: (status = null) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return request(`/api/jobs${query}`);
  },

  getJobDetail: (jobId) => request(`/api/jobs/${jobId}`),

  getJobResume: (jobId) => request(`/api/jobs/${jobId}/resume`),

  analyzeJob: (payload) => request('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),

  updateJobStatus: (jobId, newStatus, notes = '') => request(`/api/jobs/${jobId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: newStatus, notes }),
  }),

  deleteJob: (jobId) => request(`/api/jobs/${jobId}`, {
    method: 'DELETE',
  }),

  // Profile
  getProfile: () => request('/api/profile'),

  updateProfile: (profileData) => request('/api/profile', {
    method: 'PUT',
    body: JSON.stringify(profileData),
  }),

  uploadResume: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/api/profile/upload-resume`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      let errDetail = 'Failed to upload resume';
      try {
        const errJson = await response.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new Error(errDetail);
    }
    return response.json();
  },

  downloadMasterResumePdfUrl: () => `${API_BASE}/api/profile/download-resume-pdf`,
  downloadTailoredResumePdfUrl: (jobId) => `${API_BASE}/api/jobs/${jobId}/tailored-resume-pdf`,

  // Autonomous Discovery (Phase 3)
  discoverJobs: (params = {}) => request('/api/discover', {
    method: 'POST',
    body: JSON.stringify(params),
  }),

  // Application Workflow (Phase 4)
  triggerApply: (jobId, mode = 'assisted', portalName = 'Naukri 1-Click Apply') => request('/api/workflow/apply', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId, mode, portal_name: portalName }),
  }),

  resumeWorkflow: (threadId, approved = true, reason = '') => request(`/api/workflow/${threadId}/resume`, {
    method: 'POST',
    body: JSON.stringify({ approved, reason }),
  }),

  getQABank: () => request('/api/workflow/qa'),

  saveQAItem: (question, answer, category = 'General') => request('/api/workflow/qa', {
    method: 'POST',
    body: JSON.stringify({ question, answer, category }),
  }),

  // Sub-Phase 5.4: Account Connection Settings
  getSettings: () => request('/api/settings'),

  updateSettings: (payload) => request('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),

  // Auto-Pilot Autonomous Background Engine
  getAutopilotStatus: () => request('/api/autopilot/status'),
  runAutopilotNow: () => request('/api/autopilot/run-now', { method: 'POST' }),

  // Portal Persistent Session (Naukri Safe OTP Login)
  getNaukriSessionStatus: () => request('/api/portals/naukri/session-status'),
  launchNaukriSession: () => request('/api/portals/naukri/launch-session', { method: 'POST' }),

  // Sub-Phase 5.1: Server-Sent Events (SSE) Real-Time Subscription
  subscribeToEvents: (topic = 'all', onEvent, onError) => {
    const url = `${API_BASE}/api/events/stream?topic=${encodeURIComponent(topic)}`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (onEvent) onEvent(data, e.type || 'message');
      } catch (err) {
        // Heartbeat comments or non-JSON
      }
    };

    const eventTypes = ['workflow_step', 'discovery_progress', 'system_event'];
    eventTypes.forEach((type) => {
      eventSource.addEventListener(type, (e) => {
        try {
          const data = JSON.parse(e.data);
          if (onEvent) onEvent(data, type);
        } catch (err) {
          console.debug(`SSE error parsing ${type}:`, err);
        }
      });
    });

    eventSource.onerror = (err) => {
      if (onError) onError(err);
    };

    return () => {
      eventSource.close();
    };
  },
};
