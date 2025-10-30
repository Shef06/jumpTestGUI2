<script>
  import { createEventDispatcher } from 'svelte';
  import { appState } from './stores.js';
  
  export let currentStep = 1;
  
  const dispatch = createEventDispatcher();
  
  let selectedFile = null;
  let isUploading = false;
  let uploadProgress = 0;
  let fps = 30;
  let personHeight = 170;
  let bodyMass = 70;
  let errorMessage = '';
  let isCalibrating = false;
  let isAnalyzing = false;
  let isSaving = false;
  // Camera selection modal state
  let showCameraModal = false;
  let availableCameras = [];
  let selectedCamera = null;
  let loadingCameras = false;
  let cameraError = '';
  
  // Step 1: Upload/Record Video
  async function handleFileSelect(event) {
    selectedFile = event.target.files[0];
    if (selectedFile) {
      await uploadVideo();
    }
  }
  
  async function uploadVideo() {
    if (!selectedFile) return;
    
    isUploading = true;
    errorMessage = '';
    
    const formData = new FormData();
    formData.append('video', selectedFile);
    
    try {
      const response = await fetch('http://localhost:5000/api/video/upload', {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (data.success) {
        fps = Math.round(data.fps) || 30;
        dispatch('stepComplete', { step: 1, data });
      } else {
        errorMessage = data.error || 'Errore caricamento video';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione al server';
    } finally {
      isUploading = false;
    }
  }
  
  async function startRecording() {
    try {
      const response = await fetch('http://localhost:5000/api/recording/start', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        appState.update(s => ({ ...s, isRecording: true }));
      } else {
        errorMessage = data.error || 'Errore avvio registrazione';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione al server';
    }
  }

  function openCameraModal() {
    cameraError = '';
    showCameraModal = true;
    loadCameras();
  }

  async function loadCameras() {
    loadingCameras = true;
    availableCameras = [];
    selectedCamera = null;
    try {
      const res = await fetch('http://localhost:5000/api/cameras');
      const data = await res.json();
      if (Array.isArray(data.cameras) && data.cameras.length > 0) {
        availableCameras = data.cameras;
        selectedCamera = data.cameras[0];
      } else {
        cameraError = 'Nessuna fotocamera trovata';
      }
    } catch (e) {
      cameraError = 'Errore rilevamento fotocamere';
    } finally {
      loadingCameras = false;
    }
  }

  async function confirmCameraAndStart() {
    cameraError = '';
    if (selectedCamera === null || selectedCamera === undefined) {
      cameraError = 'Seleziona una fotocamera';
      return;
    }
    try {
      await fetch('http://localhost:5000/api/settings/camera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: selectedCamera })
      });
      showCameraModal = false;
      await startRecording();
    } catch (e) {
      cameraError = 'Errore impostazione fotocamera';
    }
  }
  
  async function stopRecording() {
    try {
      const response = await fetch('http://localhost:5000/api/recording/stop', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        appState.update(s => ({ ...s, isRecording: false }));
        dispatch('stepComplete', { step: 1, data });
      }
    } catch (error) {
      errorMessage = 'Errore stop registrazione';
    }
  }
  
  // Step 2: Calibration + Analysis
  async function startCalibrationAndAnalysis() {
    errorMessage = '';
    
    // Set FPS
    try {
      await fetch('http://localhost:5000/api/settings/fps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps })
      });
      
      await fetch('http://localhost:5000/api/settings/height', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ height: personHeight })
      });
      
      await fetch('http://localhost:5000/api/settings/mass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mass: bodyMass })
      });
    } catch (error) {
      errorMessage = 'Errore impostazioni';
      return;
    }
    
    // Start calibration
    try {
      const response = await fetch('http://localhost:5000/api/calibration/start', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        isCalibrating = true;
        appState.update(s => ({ ...s, isCalibrating: true }));
        checkCalibrationStatus();
      } else {
        errorMessage = data.error || 'Errore calibrazione';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione';
    }
  }
  
  async function checkCalibrationStatus() {
    const interval = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:5000/api/calibration/status');
        const data = await response.json();
        
        if (data.success && !data.in_progress) {
          clearInterval(interval);
          isCalibrating = false;
          appState.update(s => ({ ...s, isCalibrating: false }));
          dispatch('stepComplete', { step: 2, data });
        } else if (data.success === false && !data.in_progress) {
          clearInterval(interval);
          isCalibrating = false;
          appState.update(s => ({ ...s, isCalibrating: false }));
          errorMessage = 'Calibrazione fallita';
        }
      } catch (error) {
        clearInterval(interval);
        isCalibrating = false;
        errorMessage = 'Errore verifica calibrazione';
      }
    }, 500);
  }
  
  // Step 3: Analysis
  async function startAnalysis() {
    errorMessage = '';
    
    try {
      const response = await fetch('http://localhost:5000/api/analysis/start', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        isAnalyzing = true;
        appState.update(s => ({ ...s, isAnalyzing: true }));
        checkAnalysisStatus();
      } else {
        errorMessage = data.error || 'Errore avvio analisi';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione';
    }
  }
  
  async function checkAnalysisStatus() {
    const interval = setInterval(async () => {
      try {
        const statusResponse = await fetch('http://localhost:5000/api/analysis/status');
        const statusData = await statusResponse.json();
        
        if (!statusData.is_analyzing) {
          clearInterval(interval);
          
          // Get final results
          const resultsResponse = await fetch('http://localhost:5000/api/analysis/results');
          const resultsData = await resultsResponse.json();
          
          if (resultsData.success) {
            isAnalyzing = false;
            appState.update(s => ({ ...s, isAnalyzing: false }));
            dispatch('stepComplete', { 
              step: 3, 
              data: {
                ...resultsData.results,
                trajectory: resultsData.trajectory,
                velocity: resultsData.velocity
              }
            });
          }
        }
      } catch (error) {
        // Continue polling
      }
    }, 500);
  }
  
  async function pauseAnalysis() {
    try {
      await fetch('http://localhost:5000/api/analysis/pause', { method: 'POST' });
      appState.update(s => ({ ...s, isPaused: true }));
    } catch (error) {}
  }
  
  async function resumeAnalysis() {
    try {
      await fetch('http://localhost:5000/api/analysis/resume', { method: 'POST' });
      appState.update(s => ({ ...s, isPaused: false }));
    } catch (error) {}
  }

  function goBack() {
    dispatch('goBack');
  }

  async function startAnalysisFromStep2() {
    errorMessage = '';
    
    // Set FPS, height, and mass
    try {
      await fetch('http://localhost:5000/api/settings/fps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps })
      });
      
      await fetch('http://localhost:5000/api/settings/height', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ height: personHeight })
      });
      
      await fetch('http://localhost:5000/api/settings/mass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mass: bodyMass })
      });
    } catch (error) {
      errorMessage = 'Errore impostazioni';
      return;
    }
    
    // Start calibration
    try {
      const response = await fetch('http://localhost:5000/api/calibration/start', {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        isCalibrating = true;
        appState.update(s => ({ ...s, isCalibrating: true }));
        checkCalibrationAndStartAnalysis();
      } else {
        errorMessage = data.error || 'Errore calibrazione';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione';
    }
  }

  async function checkCalibrationAndStartAnalysis() {
    const interval = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:5000/api/calibration/status');
        const data = await response.json();
        
        if (data.success && !data.in_progress) {
          clearInterval(interval);
          isCalibrating = false;
          appState.update(s => ({ ...s, isCalibrating: false }));
          
          // Passa allo step 3 (analisi) mostrando i valori real-time
          dispatch('stepComplete', { step: 2, data });
          
          // Automatically start analysis after calibration
          await startAnalysis();
        } else if (data.success === false && !data.in_progress) {
          clearInterval(interval);
          isCalibrating = false;
          appState.update(s => ({ ...s, isCalibrating: false }));
          errorMessage = 'Calibrazione fallita';
        }
      } catch (error) {
        clearInterval(interval);
        isCalibrating = false;
        errorMessage = 'Errore verifica calibrazione';
      }
    }, 500);
  }
</script>

<div class="step-container bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
  <div class="step-header bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-4">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-xl font-semibold text-white">Step Holder</h2>
        <p class="text-purple-100 text-sm mt-1">Step {currentStep} di 3</p>
      </div>
      {#if currentStep > 1}
        <button
          on:click={goBack}
          class="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg transition-all duration-200 flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Indietro
        </button>
      {/if}
    </div>
  </div>
  
  <div class="step-content p-6 space-y-6">
    {#if showCameraModal}
      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div class="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md shadow-2xl">
          <div class="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
            <h4 class="text-white font-semibold">Seleziona fotocamera</h4>
            <button class="text-slate-300 hover:text-white" on:click={() => (showCameraModal = false)}>
              ✕
            </button>
          </div>
          <div class="p-6 space-y-4">
            {#if cameraError}
              <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-3 text-red-300 text-sm">{cameraError}</div>
            {/if}
            {#if loadingCameras}
              <p class="text-slate-300">Caricamento fotocamere...</p>
            {:else}
              {#if availableCameras.length > 0}
                <label for="camera-select" class="block text-sm font-medium text-slate-300 mb-2">Fotocamera</label>
                <select id="camera-select" class="input-field" bind:value={selectedCamera}>
                  {#each availableCameras as cam}
                    <option value={cam}>Camera {cam}</option>
                  {/each}
                </select>
              {:else}
                <p class="text-slate-400">Nessuna fotocamera disponibile.</p>
              {/if}
            {/if}
          </div>
          <div class="px-6 py-4 border-t border-slate-700 flex gap-2 justify-end">
            <button class="btn-secondary" on:click={() => (showCameraModal = false)}>Annulla</button>
            <button class="btn-primary" disabled={loadingCameras || availableCameras.length === 0} on:click={confirmCameraAndStart}>
              Conferma e registra
            </button>
          </div>
        </div>
      </div>
    {/if}
    {#if errorMessage}
      <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-4">
        <p class="text-red-400 text-sm">{errorMessage}</p>
      </div>
    {/if}
    
    <!-- Step 1: Upload/Record Video -->
    {#if currentStep === 1}
      <div class="space-y-4">
        <h3 class="text-lg font-semibold text-white mb-4">1. Carica o Registra Video</h3>
        
        <label class="block">
          <input
            type="file"
            accept="video/*"
            on:change={handleFileSelect}
            disabled={isUploading || $appState.isRecording}
            class="hidden"
          />
          <div class="btn-primary cursor-pointer text-center {isUploading ? 'opacity-50' : ''}">
            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            {isUploading ? 'Caricamento...' : 'Carica Video'}
          </div>
        </label>
        
        <div class="text-center text-slate-400 text-sm">oppure</div>
        
        {#if !$appState.isRecording}
          <button
            on:click={openCameraModal}
            class="btn-secondary w-full"
          >
            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Registra Video
          </button>
        {:else}
          <button
            on:click={stopRecording}
            class="btn-danger w-full"
          >
            <svg class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" />
            </svg>
            Ferma Registrazione
          </button>
        {/if}
      </div>
    {/if}
    
    <!-- Step 2: Calibration -->
    {#if currentStep === 2}
      <div class="space-y-4">
        <h3 class="text-lg font-semibold text-white mb-4">2. Calibrazione Sistema</h3>
        
        <div>
          <label for="fps-input" class="block text-sm font-medium text-slate-300 mb-2">
            FPS Video
          </label>
          <input
            id="fps-input"
            type="number"
            bind:value={fps}
            min="1"
            max="240"
            disabled={isCalibrating}
            class="input-field"
          />
          <p class="text-slate-500 text-xs mt-1">Frame per secondo del video</p>
        </div>
        
        <div>
          <label for="height-input" class="block text-sm font-medium text-slate-300 mb-2">
            Altezza Persona (cm)
          </label>
          <input
            id="height-input"
            type="number"
            bind:value={personHeight}
            min="100"
            max="250"
            disabled={isCalibrating}
            class="input-field"
          />
          <p class="text-slate-500 text-xs mt-1">Altezza reale della persona</p>
        </div>
        
        <div>
          <label for="mass-input" class="block text-sm font-medium text-slate-300 mb-2">
            Massa Corporea (kg)
          </label>
          <input
            id="mass-input"
            type="number"
            bind:value={bodyMass}
            min="40"
            max="150"
            disabled={isCalibrating}
            class="input-field"
          />
          <p class="text-slate-500 text-xs mt-1">Peso della persona</p>
        </div>
        
        <button
          on:click={startAnalysisFromStep2}
          disabled={isCalibrating}
          class="btn-primary w-full {isCalibrating ? 'opacity-50' : ''}"
        >
          {isCalibrating ? 'Calibrazione e Analisi in corso...' : 'Avvia Analisi'}
        </button>
        
        {#if isCalibrating}
          <div class="bg-blue-500/10 border border-blue-500/50 rounded-lg p-4">
            <p class="text-blue-400 text-sm">Sistema in calibrazione. Assicurati che la persona sia in posizione eretta nel frame.</p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Step 3: Analysis -->
    {#if currentStep === 3}
      <div class="space-y-4">
        <h3 class="text-lg font-semibold text-white mb-4">3. Analisi Salto</h3>
        
        {#if !isAnalyzing}
          <button
            on:click={startAnalysis}
            class="btn-primary w-full"
          >
            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Avvia Analisi
          </button>
        {:else}
          <div class="bg-green-500/10 border border-green-500/50 rounded-lg p-4">
            <p class="text-green-400 text-sm font-medium">Analisi in corso...</p>
            <p class="text-slate-400 text-xs mt-1">Il sistema sta elaborando il salto</p>
          </div>
        {/if}

        <!-- Real-time data display: visibile anche prima che partano i dati -->
        <div class="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
          <h4 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">Dati in Tempo Reale</h4>
          <div class="grid grid-cols-2 gap-3">
            <div class="text-center">
              <p class="text-slate-400 text-xs uppercase tracking-wide mb-1">Altezza Corrente</p>
              <p class="text-xl font-bold text-blue-400">{($appState.realtimeData?.current_height ?? 0)} cm</p>
            </div>
            <div class="text-center">
              <p class="text-slate-400 text-xs uppercase tracking-wide mb-1">Altezza Max</p>
              <p class="text-xl font-bold text-green-400">{($appState.realtimeData?.max_height ?? 0)} cm</p>
            </div>
            <div class="text-center">
              <p class="text-slate-400 text-xs uppercase tracking-wide mb-1">Velocità Decollo</p>
              <p class="text-xl font-bold text-purple-400">{($appState.realtimeData?.takeoff_velocity ?? 0)} cm/s</p>
            </div>
            <div class="text-center">
              <p class="text-slate-400 text-xs uppercase tracking-wide mb-1">Potenza Est.</p>
              <p class="text-xl font-bold text-yellow-400">{($appState.realtimeData?.estimated_power ?? 0)} W</p>
            </div>
          </div>
        </div>

        {#if isAnalyzing}
          <div class="flex gap-2">
            {#if $appState.isPaused}
              <button
                on:click={resumeAnalysis}
                class="btn-secondary flex-1"
              >
                Riprendi
              </button>
            {:else}
              <button
                on:click={pauseAnalysis}
                class="btn-secondary flex-1"
              >
                Pausa
              </button>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Progress indicator -->
    <div class="mt-8 pt-6 border-t border-slate-700">
      <div class="flex justify-between items-center mb-2">
        <span class="text-xs text-slate-400">Progresso</span>
        <span class="text-xs text-slate-400">{currentStep}/3</span>
      </div>
      <div class="w-full bg-slate-700 rounded-full h-2">
        <div
          class="bg-gradient-to-r from-purple-600 to-pink-600 h-2 rounded-full transition-all duration-300"
          style="width: {(currentStep / 3) * 100}%"
        ></div>
      </div>
    </div>
  </div>
</div>

<style>
</style>