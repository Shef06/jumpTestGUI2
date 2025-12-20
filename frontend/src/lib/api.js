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
  saveResults(testId, jumpData = null) {
    const body = { testId };
    if (jumpData) {
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
  
  /**
   * Carica i dati del giocatore dall'API esterna
   * @param {number} playerId - ID del giocatore
   * @param {string} sessionId - Session ID per l'autenticazione
   * @returns {Promise<Object>} Dati del giocatore o errore
   */
  async getPlayerData(playerId, sessionId) {
    try {
      //document.cookie = `session_id=${sessionId}; path=/`
      // SCONSIGLIATO PER I COOKIE DI SESSIONE
      document.cookie = `session_id=${sessionId}; path=/api/players`;
      const response = await fetch(`http://localhost:5173/api/players/${playerId}`, {
        method: 'GET',
        credentials: 'include', // ⭐ manda automaticamente i cookie del dominio
        headers: {
          'Accept': '*/*'
          // ❌ niente header Cookie: il browser lo blocca
        }
      });
  
      if (!response.ok) {
        return { success: false, error: `Errore HTTP: ${response.status}` };
      }
      
      const data = await response.json();
      
      if (data?.data?.info) {
        return {
          success: true,
          data: {
            height_cm: data.data.info.height_cm,
            weight_kg: data.data.info.weight_kg,
            name: data.data.info.name,
            surname: data.data.info.surname,
            position: data.data.info.position
          }
        };
      }
      
      return { success: false, error: 'Dati giocatore non validi' };
    } catch (error) {
      return { success: false, error: `Errore di connessione: ${error.message}` };
    }
  }
  
};





