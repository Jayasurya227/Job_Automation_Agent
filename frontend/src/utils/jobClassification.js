/**
 * Utility for robust job application classification and external link handling.
 * Ensures consistent behavior across KanbanBoard, JobModal, TableView, and App.
 */

export function getJobApplyClassification(job) {
  if (!job) {
    return {
      isExternal: false,
      is1Click: false,
      isApplied: false,
      hasDirectUrl: false,
      applyUrl: ''
    };
  }

  const isApplied = job.status === 'Applied';
  const notes = (job.notes || job.applications?.[0]?.notes || '').toLowerCase();
  const appStatus = job.applications?.[0]?.status;
  const rawUrl = (job.job_url || '').trim();
  const hasDirectUrl = Boolean(rawUrl && rawUrl.startsWith('http'));

  // 1. External Detection (Authority: Explicit external tags or off-portal URLs)
  const isExplicitExternal = Boolean(
    notes.includes('external company portal') ||
    notes.includes('external portal') ||
    notes.includes('external site') ||
    notes.includes('direct employer application required') ||
    notes.includes('direct application required') ||
    appStatus === 'EXTERNAL_SITE' ||
    (notes.includes('external') && !notes.startsWith('1-click')) ||
    (hasDirectUrl && !rawUrl.includes('naukri.com') && !rawUrl.includes('indeed.com'))
  );

  // 2. 1-Click Detection
  const isExplicit1Click = !isExplicitExternal && Boolean(
    notes.startsWith('1-click') ||
    notes.includes('1-click apply ready') ||
    notes.includes('easy apply')
  );

  const isExternal = !isApplied && (isExplicitExternal || (!isExplicit1Click && Boolean(
    notes.includes('external') ||
    appStatus === 'EXTERNAL_SITE'
  )));

  const is1Click = !isApplied && !isExternal;

  return {
    isExternal,
    is1Click,
    isApplied,
    hasDirectUrl,
    applyUrl: rawUrl
  };
}

/**
 * Open external job posting in a new window/tab safely and reliably.
 */
export function openExternalJobLink(jobUrl) {
  if (!jobUrl) return false;
  try {
    const newWindow = window.open(jobUrl, '_blank', 'noopener,noreferrer');
    if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
      // If popup blocker intervened, fallback to top-level anchor click
      const a = document.createElement('a');
      a.href = jobUrl;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    return true;
  } catch (err) {
    console.error('Failed to open external URL:', err);
    return false;
  }
}

