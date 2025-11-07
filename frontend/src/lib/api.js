const BASE = 'http://localhost:5000';

async function jsonFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
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
  analysisData() { return jsonFetch('/api/analysis/data'); }
};





