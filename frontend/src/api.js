/**
 * Autonomous Job Automation Agent - Central API Client
 * Connects Frontend directly to FastAPI Backend endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
// Must match API_TOKEN in backend/.env. Leave unset when the backend has no API_TOKEN.
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

// EventSource, <a href> and <iframe> cannot send headers, so the token goes in the query string.
function withToken(url) {
  if (!API_TOKEN) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}api_token=${encodeURIComponent(API_TOKEN)}`;
}

function authHeaders() {
  return API_TOKEN ? { 'X-API-Token': API_TOKEN } : {};
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...authHeaders(),
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

  // Pipeline Metrics
  getMetrics: () => request('/api/metrics'),

  // Jobs
  getJobs: (status = null, daysLimit = 7) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (daysLimit !== null && daysLimit !== undefined) params.append('days_limit', daysLimit);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/jobs${query}`);
  },

  getJobsHistory: (year = null, month = null) => {
    const params = new URLSearchParams();
    if (year) params.append('year', year);
    if (month) params.append('month', month);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/jobs/history${query}`);
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
      headers: authHeaders(),
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

  downloadMasterResumePdfUrl: () => withToken(`${API_BASE}/api/profile/download-resume-pdf`),
  downloadTailoredResumePdfUrl: (jobId) => withToken(`${API_BASE}/api/jobs/${jobId}/tailored-resume-pdf`),

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
  connectNaukriMobile: (data) => request('/api/portals/naukri/connect-mobile', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  verifyNaukriMobileOtp: (data) => request('/api/portals/naukri/verify-otp', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  cancelNaukriMobileSession: (sessionId) => request('/api/portals/naukri/cancel-mobile', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  }),

  // Portal Persistent Session (Indeed Safe Login)
  getIndeedSessionStatus: () => request('/api/portals/indeed/session-status'),
  launchIndeedSession: () => request('/api/portals/indeed/launch-session', { method: 'POST' }),

  // Sub-Phase 5.1: Server-Sent Events (SSE) Real-Time Subscription
  subscribeToEvents: (topic = 'all', onEvent, onError) => {
    const url = withToken(`${API_BASE}/api/events/stream?topic=${encodeURIComponent(topic)}`);
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
