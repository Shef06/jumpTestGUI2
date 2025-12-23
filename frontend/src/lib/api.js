// Determine backend URL based on environment
// When opening index.html directly (file://), use absolute URL
// When served from a server, could use relative paths (but Flask is on different port)
export const getBackendUrl = () => {
  // Check if we have a custom backend URL set (e.g., from environment or config)
  if (typeof window !== 'undefined' && window.BACKEND_URL) {
    return window.BACKEND_URL;
  }
  // Default to localhost:5000 (Flask backend)
  return 'http://localhost:5000';
};

const BASE = getBackendUrl();

async function jsonFetch(path, options = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, options);
  try {
    return await res.json();
  } catch (_) {
    return {};
  }
}

export const api = {
  setCamera(index) {
    return jsonFetch('/api/settings/camera', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index: Number(index) })
    });
  },
  setFps(fps) {
    return jsonFetch('/api/settings/fps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fps })
    });
  },
  setHeight(height) {
    return jsonFetch('/api/settings/height', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ height })
    });
  },
  setMass(mass) {
    return jsonFetch('/api/settings/mass', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mass })
    });
  },
  startRecording() { return jsonFetch('/api/recording/start', { method: 'POST' }); },
  stopRecording() { return jsonFetch('/api/recording/stop', { method: 'POST' }); },
  startCalibration() { return jsonFetch('/api/calibration/start', { method: 'POST' }); },
  calibrationStatus() { return jsonFetch('/api/calibration/status'); },
  startAnalysis() { return jsonFetch('/api/analysis/start', { method: 'POST' }); },
  analysisStatus() { return jsonFetch('/api/analysis/status'); },
  analysisResults() { return jsonFetch('/api/analysis/results'); },
  pauseAnalysis() { return jsonFetch('/api/analysis/pause', { method: 'POST' }); },
  resumeAnalysis() { return jsonFetch('/api/analysis/resume', { method: 'POST' }); },
  stopAnalysis() { return jsonFetch('/api/analysis/stop', { method: 'POST' }); },
  videoFrame() { return jsonFetch('/api/video/frame'); },
  analysisData() { return jsonFetch('/api/analysis/data'); },
  saveResults(testId, jumpData = null, jumpId = null, action = 'add') {
    const body = { testId };
    if (jumpData) {
      body.jumpId = jumpId;
      body.action = action; // 'add' o 'remove'
      body.results = jumpData.results;
      body.trajectory = jumpData.trajectory;
      body.velocity = jumpData.velocity;
      body.settings = jumpData.settings;
    }
    return jsonFetch('/api/results/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  },
  
};





