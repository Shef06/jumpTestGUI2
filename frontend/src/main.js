// Import CSS and App component (static imports for IIFE compatibility)
import './app.css';
import App from './App.svelte';

// Mark that module is loading
window.__APP_LOADING__ = true;

// Initialize app when DOM is ready
function initApp() {
  try {
    const appElement = document.getElementById('app');
    if (!appElement) {
      throw new Error('Elemento #app non trovato nel DOM');
    }

    // Clear loading message
    appElement.innerHTML = '';

    const app = new App({
      target: appElement,
    });

    // Mark that app loaded successfully
    window.__APP_LOADED__ = true;
    window.__APP_LOADING__ = false;
  } catch (error) {
    console.error('Errore durante l\'inizializzazione dell\'app:', error);
    window.__APP_LOADING__ = false;
    
    const appElement = document.getElementById('app');
    if (appElement) {
      appElement.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 100vh; background: #0f172a; color: white; font-family: sans-serif; padding: 20px;">
          <div style="text-align: center; max-width: 600px;">
            <h1 style="color: #ef4444; margin-bottom: 20px;">Errore di Caricamento</h1>
            <p style="color: #94a3b8; margin-bottom: 10px;">Si è verificato un errore durante il caricamento dell'applicazione.</p>
            <p style="color: #64748b; font-size: 14px; margin-top: 20px; word-break: break-word;">${error.message || 'Errore sconosciuto'}</p>
            <p style="color: #64748b; font-size: 12px; margin-top: 10px;">Stack: ${error.stack || 'N/A'}</p>
            <p style="color: #64748b; font-size: 12px; margin-top: 10px;">Apri la console del browser (F12) per maggiori dettagli.</p>
          </div>
        </div>
      `;
    }
  }
}

// Wait for DOM to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  // DOM is already ready
  initApp();
}