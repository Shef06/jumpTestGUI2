<script>
  import { createEventDispatcher } from 'svelte';
  import { appState, setLocalVideoUrl, setCameraPreview, setPreviewStream, clearPreviewStream, setInputMode } from './stores.js';
  import { enumerateCameras, openPreviewByIndex, stopStream } from './camera.js';
  import { api, getBackendUrl } from './api.js';
  import CameraModal from './CameraModal.svelte';
  
  export let currentStep = 1;
  
  const dispatch = createEventDispatcher();
  
  let selectedFile = null;
  let isUploading = false;
  let fps = 30;
  let personHeight = Number(sessionStorage.getItem('playerHeight')) || 192;
  let bodyMass = Number(sessionStorage.getItem('playerWeight')) || 97;
  let errorMessage = '';
  let isCalibrating = false;
  let isAnalyzing = false;
  
  // Camera selection state
  let showCameraModal = false;
  let availableCameras = []; 
  let selectedCamera = null; 
  let loadingCameras = false;
  let cameraError = '';

  // Player data state (placeholder per future integrazioni)
  let playerId = 1;
  let sessionId = '';
  
  // --- Gestione File & Upload (Step 1) ---
  async function handleFileSelect(event) {
    selectedFile = event.target.files[0];
    if (selectedFile) {
      // Leggi altezza e peso da sessionStorage quando viene caricato il video
      const height = sessionStorage.getItem('playerHeight'); // in cm
      const weight = sessionStorage.getItem('playerWeight'); // in kg
      
      if (height) {
        personHeight = Number(height) || personHeight;
      }
      if (weight) {
        bodyMass = Number(weight) || bodyMass;
      }
      
      try {
        const objectUrl = URL.createObjectURL(selectedFile);
        setLocalVideoUrl(objectUrl);
      } catch (e) {}
      setInputMode('upload');
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
      const response = await fetch(`${getBackendUrl()}/api/video/upload`, { method: 'POST', body: formData });
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
  
  // --- Gestione Camera & Registrazione (Step 1) ---
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
      const videoInputs = await enumerateCameras();
      if (videoInputs.length > 0) {
        availableCameras = videoInputs;
        selectedCamera = 0;
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
      showCameraModal = false;
      try {
        stopStream($appState.previewStream);
        const stream = await openPreviewByIndex(Number(selectedCamera), availableCameras);
        setPreviewStream(stream);
        setCameraPreview(true);
        setInputMode('camera');
      } catch (err) {
        cameraError = 'Impossibile avviare l\'anteprima fotocamera';
      }
    } catch (e) {
      cameraError = 'Errore apertura anteprima';
    }
  }

  async function startRecording() {
    try {
      if (selectedCamera !== null && selectedCamera !== undefined) {
        try { await api.setCamera(Number(selectedCamera)); } catch (e) { errorMessage = 'Errore impostazione fotocamera'; return; }
      }
      try { stopStream($appState.previewStream); } catch (_) {}
      clearPreviewStream();
      setCameraPreview(false);

      const data = await api.startRecording();
      if (data.success) {
        appState.update(s => ({ ...s, isRecording: true }));
      } else {
        errorMessage = data.error || 'Errore avvio registrazione';
      }
    } catch (error) {
      errorMessage = 'Errore di connessione al server';
    }
  }
  
  async function stopRecording() {
    try {
      const response = await fetch(`${getBackendUrl()}/api/recording/stop`, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        appState.update(s => ({ ...s, isRecording: false }));
        dispatch('stepComplete', { step: 1, data });
      }
    } catch (error) {
      errorMessage = 'Errore stop registrazione';
    }
  }
  
  // --- Calibrazione & Analisi (Step 2) ---
  async function startAnalysisFromStep2() {
    errorMessage = '';
    try {
      await api.setFps(fps);
      await api.setHeight(personHeight);
      await api.setMass(bodyMass);
    } catch (error) {
      errorMessage = 'Errore impostazioni';
      return;
    }
    
    // Verifica esistenza video
    try {
      const info = await fetch(`${getBackendUrl()}/api/video/info`).then(r => r.json());
      if (!info?.video_path) {
        errorMessage = 'Nessun video disponibile. Registra o carica prima il video.';
        return;
      }
    } catch (_) {
      errorMessage = 'Errore verifica video disponibile';
      return;
    }

    try {
      const data = await api.startCalibration();
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
        const data = await api.calibrationStatus();
        if (data.success && !data.in_progress) {
          clearInterval(interval);
          isCalibrating = false;
          appState.update(s => ({ ...s, isCalibrating: false }));
          dispatch('stepComplete', { step: 2, data });
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

  // --- Analisi (Step 3) ---
  async function startAnalysis() {
    errorMessage = '';
    try {
      const data = await api.startAnalysis();
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
        const statusData = await api.analysisStatus();
        if (!statusData.is_analyzing) {
          clearInterval(interval);
          const resultsData = await api.analysisResults();
          if (resultsData.success) {
            isAnalyzing = false;
            appState.update(s => ({ ...s, isAnalyzing: false }));
            dispatch('stepComplete', { 
              step: 3, 
              data: {
                ...resultsData.results,
                trajectory: resultsData.trajectory,
                velocity: resultsData.velocity,
                phase_times: resultsData.phase_times
              }
            });
          }
        }
      } catch (error) {}
    }, 500);
  }
  
  async function pauseAnalysis() {
    try {
      await api.pauseAnalysis();
      appState.update(s => ({ ...s, isPaused: true }));
    } catch (error) {}
  }
  
  async function resumeAnalysis() {
    try {
      await api.resumeAnalysis();
      appState.update(s => ({ ...s, isPaused: false }));
    } catch (error) {}
  }

  async function cancelAnalysis() {
    try { await api.stopAnalysis(); } catch (error) {}
    dispatch('cancelToStep1');
  }

  function goBack() {
    if (currentStep === 1 && $appState.isCameraPreview) {
      goBackFromCameraPreview();
    } else {
      dispatch('goBack');
    }
  }

  async function goBackFromCameraPreview() {
    try { stopStream($appState.previewStream); } catch (e) {}
    clearPreviewStream();
    setCameraPreview(false);
    setInputMode('none');
    selectedCamera = null;
  }
</script>

<div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden relative ring-1 ring-white/5 flex flex-col h-full w-full" role="region" aria-label="Pannello controllo analisi">
  
  <!-- Header Fisso (Sticky style) -->
  <div class="shrink-0 bg-slate-900 z-10 border-b border-slate-800">
    <div class="px-5 py-4 flex justify-between items-center">
      <div>
        <h2 class="text-sm font-bold text-white tracking-tight flex items-center gap-2">
            <span class="bg-indigo-600 w-6 h-6 rounded flex items-center justify-center text-[10px]">{currentStep}</span>
            CONFIGURAZIONE
        </h2>
        <p class="text-slate-500 text-xs mt-1 font-medium pl-8">
            {#if currentStep === 1}Acquisizione Video
            {:else if currentStep === 2}Calibrazione & Dati
            {:else}Elaborazione Analisi{/if}
        </p>
      </div>
      
      {#if currentStep > 1 || $appState.isCameraPreview}
        <button
          on:click={goBack}
          class="text-slate-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-slate-800"
          aria-label="Torna indietro"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      {/if}
    </div>

    <!-- Progress Bar Integrata -->
    <div class="w-full h-1 bg-slate-800">
        <div class="h-full bg-indigo-500 transition-all duration-500 ease-out" style="width: {(currentStep / 3) * 100}%"></div>
    </div>
  </div>

  <!-- Contenuto Scrollabile -->
  <div class="flex-1 overflow-y-auto p-5 custom-scrollbar bg-slate-900/50 space-y-6">
    
    <CameraModal
      show={showCameraModal}
      loading={loadingCameras}
      cameras={availableCameras}
      bind:selectedIndex={selectedCamera}
      error={cameraError}
      on:close={() => (showCameraModal = false)}
      on:confirm={confirmCameraAndStart}
      on:select={(e) => (selectedCamera = e.detail.index)}
    />

    {#if errorMessage}
      <div class="bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-start gap-3">
        <svg class="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p class="text-red-400 text-sm font-medium">{errorMessage}</p>
      </div>
    {/if}
    
    <!-- Step 1: Upload/Record Video -->
    {#if currentStep === 1}
      <div class="space-y-5 animate-in fade-in slide-in-from-right-2 duration-300">
        
        {#if $appState.inputMode !== 'camera'}
          <div class="bg-slate-800/50 border border-slate-700 border-dashed rounded-xl p-6 text-center hover:bg-slate-800 transition-colors group cursor-pointer relative">
            <input
              type="file"
              accept="video/*"
              on:change={handleFileSelect}
              disabled={isUploading || $appState.isRecording}
              class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10 disabled:cursor-not-allowed"
            />
            <div class="flex flex-col items-center gap-3 {isUploading ? 'opacity-50' : ''}">
                <div class="w-12 h-12 rounded-full bg-slate-700 group-hover:bg-indigo-600/20 group-hover:text-indigo-400 flex items-center justify-center transition-colors text-slate-400">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                </div>
                <div>
                    <p class="text-sm font-semibold text-white group-hover:text-indigo-300 transition-colors">{isUploading ? 'Caricamento in corso...' : 'Carica un file video'}</p>
                    <p class="text-xs text-slate-500 mt-1">MP4, MOV, AVI fino a 50MB</p>
                </div>
            </div>
          </div>
          
          <div class="relative flex items-center py-2">
             <div class="grow border-t border-slate-700"></div>
             <span class="shrink-0 mx-4 text-xs text-slate-500 font-medium uppercase">Oppure</span>
             <div class="grow border-t border-slate-700"></div>
          </div>
        {/if}

        {#if !$appState.isRecording}
          <button
            on:click={openCameraModal}
            class="btn-secondary w-full flex items-center justify-center gap-2 py-3"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            { $appState.inputMode === 'camera' ? 'Cambia Sorgente Video' : 'Usa Fotocamera' }
          </button>
          
          {#if $appState.isCameraPreview}
            <div class="bg-indigo-900/20 border border-indigo-500/30 rounded-lg p-4 mt-4 animate-pulse-fade">
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></div>
                    <h4 class="text-sm font-medium text-indigo-300">Anteprima Attiva</h4>
                </div>
                <p class="text-xs text-indigo-200/70 mb-4 leading-relaxed">Posizionati correttamente nel riquadro. Quando sei pronto, avvia l'analisi.</p>
                <button
                  on:click={startRecording}
                  class="btn-primary w-full flex items-center justify-center gap-2 py-3 shadow-lg shadow-indigo-900/40"
                >
                  <div class="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                  REC & Analizza
                </button>
            </div>
          {/if}
        {:else}
          <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-6 text-center animate-pulse-fade">
              <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <div class="w-4 h-4 bg-red-500 rounded animate-pulse"></div>
              </div>
              <h3 class="text-white font-semibold mb-1">Registrazione in corso</h3>
              <p class="text-slate-400 text-xs mb-6">Esegui il salto ora...</p>
              
              <button
                on:click={stopRecording}
                class="btn-danger w-full flex items-center justify-center gap-2 py-3"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" /></svg>
                Termina Registrazione
              </button>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Step 2: Calibration -->
    {#if currentStep === 2}
      <div class="space-y-5 animate-in fade-in slide-in-from-right-2 duration-300">
        
        <!-- Parametri Input -->
        <div class="grid grid-cols-2 gap-4">
             <div class="col-span-2">
                <label for="fps-input" class="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-1.5">FPS Video</label>
                <div class="relative">
                    <input id="fps-input" type="number" bind:value={fps} min="1" max="240" disabled={isCalibrating} class="input-field pl-10 font-mono text-sm" />
                    <div class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    </div>
                </div>
             </div>

             <div>
                <label for="height-input" class="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-1.5">Altezza (cm)</label>
                <input id="height-input" type="number" bind:value={personHeight} min="100" max="250" disabled={isCalibrating} class="input-field font-mono text-sm" />
             </div>
             
             <div>
                <label for="mass-input" class="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-1.5">Massa (kg)</label>
                <input id="mass-input" type="number" bind:value={bodyMass} min="40" max="150" disabled={isCalibrating} class="input-field font-mono text-sm" />
             </div>
        </div>

        {#if isCalibrating}
          <div class="bg-indigo-900/20 border border-indigo-500/30 rounded-lg p-4 flex flex-col items-center text-center animate-pulse">
            <svg class="animate-spin h-8 w-8 text-indigo-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="text-indigo-300 text-sm font-medium">Calibrazione in corso...</p>
            <p class="text-indigo-400/60 text-xs mt-1">Mantieni il soggetto in posizione eretta</p>
          </div>
        {:else}
          <button
            on:click={startAnalysisFromStep2}
            class="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            Conferma e Avvia
          </button>
        {/if}
      </div>
    {/if}
    
    <!-- Step 3: Analysis -->
    {#if currentStep === 3}
      <div class="space-y-5 animate-in fade-in slide-in-from-right-2 duration-300">
        
        {#if isAnalyzing}
            <div class="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-4 flex items-center gap-3 animate-pulse">
                <div class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </div>
                <div>
                    <p class="text-emerald-400 text-sm font-medium">Elaborazione in corso...</p>
                    <p class="text-emerald-500/60 text-xs">Analisi traiettoria e fasi</p>
                </div>
            </div>
        {:else}
             <button on:click={startAnalysis} class="btn-primary w-full flex items-center justify-center gap-2 py-3">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                Riavvia Analisi
             </button>
        {/if}

        <!-- Real-time Data Card (Matching ResultsView Style) -->
        <div class="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden shadow-sm">
          <div class="px-4 py-2 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
            <h3 class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                Metriche Live
            </h3>
            {#if isAnalyzing}
                <div class="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
            {/if}
          </div>
          <div class="p-4 grid grid-cols-2 gap-4">
            <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wide font-semibold mb-0.5">Alt. Corrente</span>
                <span class="text-lg font-mono font-bold text-blue-400">{($appState.realtimeData?.current_height ?? 0)} cm</span>
            </div>
            <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wide font-semibold mb-0.5">Alt. Max</span>
                <span class="text-lg font-mono font-bold text-emerald-400">{($appState.realtimeData?.max_height ?? 0)} cm</span>
            </div>
            <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wide font-semibold mb-0.5">Vel. Decollo</span>
                <span class="text-lg font-mono font-bold text-purple-400">{($appState.realtimeData?.takeoff_velocity ?? 0)}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wide font-semibold mb-0.5">Potenza</span>
                <span class="text-lg font-mono font-bold text-amber-400">{($appState.realtimeData?.estimated_power ?? 0)} W</span>
            </div>
          </div>
        </div>

        {#if isAnalyzing}
          <div class="grid grid-cols-2 gap-2 pt-2">
            {#if $appState.isPaused}
              <button on:click={resumeAnalysis} class="btn-secondary text-xs py-2">Riprendi</button>
            {:else}
              <button on:click={pauseAnalysis} class="btn-secondary text-xs py-2">Pausa</button>
            {/if}
            <button on:click={cancelAnalysis} class="btn-danger text-xs py-2">Stop</button>
          </div>
        {/if}
      </div>
    {/if}
    
  </div>
</div>