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
  let uploadProgress = 0;
  let fps = 30;
  let personHeight = 174;
  let bodyMass = 62;
  let errorMessage = '';
  let isCalibrating = false;
  let isAnalyzing = false;
  let isSaving = false;
  // Camera selection modal state
  let showCameraModal = false;
  let availableCameras = []; // array di MediaDeviceInfo per videoinput
  let selectedCamera = null; // indice nella lista availableCameras
  let loadingCameras = false;
  let cameraError = '';
  let playerId = 1;
  let sessionId = '94822145f84207b6792a83e2d6708c9ce009153bcb34656647de4851ce80214f';
  let isLoadingPlayer = false;
  let playerLoadError = '';
  let playerName = '';
  let hasAutoLoaded = false; // Flag per evitare caricamenti multipli
  
  // Carica automaticamente i dati del giocatore quando si entra nello Step 2
  $: if (currentStep === 2 && !hasAutoLoaded && playerId && sessionId) {
    hasAutoLoaded = true;
    loadPlayerData();
  }
  
  // Reset del flag quando si esce dallo Step 2
  $: if (currentStep !== 2) {
    hasAutoLoaded = false;
  }
  
  // Step 1: Upload/Record Video
  async function handleFileSelect(event) {
    selectedFile = event.target.files[0];
    if (selectedFile) {
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
      const response = await fetch(`${getBackendUrl()}/api/video/upload`, {
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
      // Imposta la fotocamera selezionata lato backend solo al momento dell'analisi/registrazione
      if (selectedCamera !== null && selectedCamera !== undefined) {
        try {
          await api.setCamera(Number(selectedCamera));
        } catch (e) {
          errorMessage = 'Errore impostazione fotocamera';
          return;
        }
      }

      // Stop anteprima PRIMA di avviare la registrazione lato backend
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
      // Avvia solo l'anteprima (senza registrare) con getUserMedia
      try {
        // Chiudi eventuale stream precedente
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
  
  async function stopRecording() {
    try {
      const response = await fetch(`${getBackendUrl()}/api/recording/stop`, {
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
      await api.setFps(fps);
      await api.setHeight(personHeight);
      await api.setMass(bodyMass);
    } catch (error) {
      errorMessage = 'Errore impostazioni';
      return;
    }
    // Avvia registrazione al click su Avvia Analisi e disattiva anteprima
    // Verifica che esista già un video lato backend (registrato o caricato)
    try {
      const info = await fetch(`${getBackendUrl()}/api/video/info`).then(r => r.json());
      if (!info?.video_path) {
        errorMessage = 'Nessun video disponibile: registra o carica prima il video.';
        return;
      }
    } catch (_) {
      errorMessage = 'Errore verifica video disponibile';
      return;
    }
    
    // Start calibration
    try {
      const data = await api.startCalibration();
      
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
        const data = await api.calibrationStatus();
        
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
    // Verifica che esista già un video lato backend (registrato o caricato)
    try {
      const info = await fetch(`${getBackendUrl()}/api/video/info`).then(r => r.json());
      if (!info?.video_path) {
        errorMessage = 'Nessun video disponibile: registra o carica prima il video.';
        return;
      }
    } catch (_) {
      errorMessage = 'Errore verifica video disponibile';
      return;
    }
    
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
          
          // Get final results
          const resultsData = await api.analysisResults();
          
          if (resultsData.success) {
            isAnalyzing = false;
            appState.update(s => ({ ...s, isAnalyzing: false }));
            dispatch('stepComplete', { 
              step: 3, 
              data: {
                ...resultsData.results,
                trajectory: resultsData.trajectory,
                velocity: resultsData.velocity, // Ora è la velocità derivata
                phase_times: resultsData.phase_times
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
      await fetch(`${getBackendUrl()}/api/analysis/pause`, { method: 'POST' });
      appState.update(s => ({ ...s, isPaused: true }));
    } catch (error) {}
  }
  
  async function resumeAnalysis() {
    try {
      await fetch(`${getBackendUrl()}/api/analysis/resume`, { method: 'POST' });
      appState.update(s => ({ ...s, isPaused: false }));
    } catch (error) {}
  }

  async function cancelAnalysis() {
    try {
      await fetch(`${getBackendUrl()}/api/analysis/stop`, { method: 'POST' });
    } catch (error) {}
    dispatch('cancelToStep1');
  }

  function goBack() {
    // Se siamo nello Step 1 con anteprima telecamera attiva, torna alla scelta iniziale
    if (currentStep === 1 && $appState.isCameraPreview) {
      goBackFromCameraPreview();
    } else {
      dispatch('goBack');
    }
  }

  async function goBackFromCameraPreview() {
    // Stop the preview stream
    try {
      stopStream($appState.previewStream);
    } catch (e) {}
    clearPreviewStream();
    setCameraPreview(false);
    setInputMode('none');
    selectedCamera = null;
  }

  async function startAnalysisFromStep2() {
    errorMessage = '';
    
    // Set FPS, height, and mass
    try {
      await fetch(`${getBackendUrl()}/api/settings/fps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps })
      });
      
      await fetch(`${getBackendUrl()}/api/settings/height`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ height: personHeight })
      });
      
      await fetch(`${getBackendUrl()}/api/settings/mass`, {
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
      const response = await fetch(`${getBackendUrl()}/api/calibration/start`, {
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
        const response = await fetch(`${getBackendUrl()}/api/calibration/status`);
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
  
  // Funzione per caricare i dati del giocatore
  async function loadPlayerData() {
    if (!playerId || !sessionId) {
      playerLoadError = 'Inserisci ID giocatore e Session ID';
      return;
    }
    
    isLoadingPlayer = true;
    playerLoadError = '';
    playerName = '';
    
    try {
      const result = await api.getPlayerData(Number(playerId), sessionId);
      
      if (result.success && result.data) {
        // Aggiorna i campi con i dati del giocatore
        personHeight = result.data.height_cm || personHeight;
        bodyMass = result.data.weight_kg || bodyMass;
        
        // Aggiorna anche nel backend
        await api.setHeight(personHeight);
        await api.setMass(bodyMass);
        
        // Mostra il nome del giocatore
        if (result.data.name && result.data.surname) {
          playerName = `${result.data.name} ${result.data.surname}`;
        } else if (result.data.name) {
          playerName = result.data.name;
        }
      } else {
        playerLoadError = result.error || 'Errore nel caricamento dei dati del giocatore';
      }
    } catch (error) {
      playerLoadError = `Errore: ${error.message}`;
    } finally {
      isLoadingPlayer = false;
    }
  }
</script>

<div class="step-container bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700 h-full flex flex-col" role="region" aria-label="Pannello controllo analisi">
  <div class="step-header bg-gradient-to-r from-purple-600 to-pink-600 px-4 sm:px-6 py-3 sm:py-4">
    <div class="flex justify-between items-center gap-4">
      <div>
        <h2 class="text-lg sm:text-xl font-semibold text-white">Step Holder</h2>
        <p class="text-purple-100 text-xs sm:text-sm mt-1" aria-live="polite">Step {currentStep} di 3</p>
      </div>
      {#if currentStep > 1 || $appState.isCameraPreview}
        <button
          on:click={goBack}
          class="bg-white/20 hover:bg-white/30 focus:bg-white/30 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg transition-all duration-200 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-white/50 focus:ring-offset-2 focus:ring-offset-purple-600"
          aria-label="Torna allo step precedente"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          <span class="hidden sm:inline">Indietro</span>
        </button>
      {/if}
    </div>
  </div>
  
  <div class="step-content p-3 sm:p-4 md:p-6 space-y-3 sm:space-y-4 md:space-y-6 flex-1 overflow-auto">
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
      <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-3 sm:p-4" role="alert" aria-live="assertive">
        <p class="text-red-400 text-sm">{errorMessage}</p>
      </div>
    {/if}
    
    <!-- Step 1: Upload/Record Video -->
    {#if currentStep === 1}
      <div class="space-y-4">
        <h3 class="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">
          { $appState.inputMode === 'camera' ? '1. Registra Video' : '1. Carica o Registra Video' }
        </h3>

        {#if $appState.inputMode !== 'camera'}
          <label class="block">
            <input
              type="file"
              accept="video/*"
              on:change={handleFileSelect}
              disabled={isUploading || $appState.isRecording}
              class="hidden"
              aria-label="Seleziona file video da caricare"
            />
            <div class="btn-primary cursor-pointer text-center {isUploading ? 'opacity-50' : ''}" role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && !isUploading && !$appState.isRecording && e.currentTarget.closest('label')?.querySelector('input')?.click()}>
              <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              {isUploading ? 'Caricamento...' : 'Carica Video'}
            </div>
          </label>
          <div class="text-center text-slate-400 text-sm" aria-hidden="true">oppure</div>
        {/if}

        {#if !$appState.isRecording}
          <button
            on:click={openCameraModal}
            class="btn-secondary w-full"
            aria-label={$appState.inputMode === 'camera' ? 'Cambia telecamera' : 'Apri modal selezione telecamera per registrare video'}
          >
            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            { $appState.inputMode === 'camera' ? 'Cambia Telecamera' : 'Registra Video' }
          </button>
          {#if $appState.isCameraPreview}
            <button
              on:click={startRecording}
              class="btn-primary w-full mt-3"
              aria-label="Avvia analisi video e inizia registrazione"
            >
              Analizza Video
            </button>
          {/if}
          {#if $appState.isCameraPreview}
            <div class="bg-blue-500/10 border border-blue-500/50 rounded-lg p-3 text-blue-300 text-sm" role="status" aria-live="polite">
              Anteprima fotocamera attiva. Premi "Analizza Video" per iniziare la registrazione, poi "Ferma Registrazione" al termine del salto.
            </div>
          {/if}
        {:else}
          <button
            on:click={stopRecording}
            class="btn-danger w-full"
            aria-label="Ferma registrazione video"
          >
            <svg class="w-5 h-5 inline mr-2" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
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
        <h3 class="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">2. Calibrazione Sistema</h3>
        
        <!-- Carica dati giocatore per debug -->
        <!-- <div class="bg-slate-900/50 rounded-xl p-3 sm:p-4 border border-slate-700">
          <h4 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2 sm:mb-3">Carica Dati Giocatore</h4>
          
          <div class="space-y-2 sm:space-y-3">
            <div>
              <label for="player-id-input" class="block text-sm font-medium text-slate-300 mb-2">
                ID Giocatore
              </label>
              <input
                id="player-id-input"
                type="number"
                bind:value={playerId}
                min="1"
                disabled={isCalibrating || isLoadingPlayer}
                class="input-field"
                placeholder="1"
                aria-describedby="player-id-help"
              />
              <p id="player-id-help" class="text-slate-500 text-xs mt-1">ID del giocatore da caricare</p>
            </div>
            
            <div>
              <label for="session-id-input" class="block text-sm font-medium text-slate-300 mb-2">
                Session ID
              </label>
              <input
                id="session-id-input"
                type="text"
                bind:value={sessionId}
                disabled={isCalibrating || isLoadingPlayer}
                class="input-field"
                placeholder="Session ID"
                aria-describedby="session-id-help"
              />
              <p id="session-id-help" class="text-slate-500 text-xs mt-1">Session ID per l'autenticazione</p>
            </div>
            
            <button
              on:click={loadPlayerData}
              disabled={isCalibrating || isLoadingPlayer}
              class="btn-secondary w-full"
              aria-label={isLoadingPlayer ? 'Caricamento dati in corso' : 'Carica dati giocatore'}
            >
              {#if isLoadingPlayer}
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Caricamento...
              {:else}
                <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Carica Dati Giocatore
              {/if}
            </button>
            
            {#if playerLoadError}
              <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-2 sm:p-3" role="alert" aria-live="assertive">
                <p class="text-red-400 text-xs sm:text-sm">{playerLoadError}</p>
              </div>
            {/if}
            
            {#if playerName}
              <div class="bg-green-500/10 border border-green-500/50 rounded-lg p-2 sm:p-3" role="status" aria-live="polite">
                <p class="text-green-400 text-xs sm:text-sm font-medium">Dati caricati per: {playerName}</p>
                <p class="text-slate-400 text-xs mt-1">Altezza e peso aggiornati automaticamente</p>
              </div>
            {/if}
          </div>
        </div> -->
        
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
            aria-describedby="fps-help"
          />
          <p id="fps-help" class="text-slate-500 text-xs mt-1">Frame per secondo del video</p>
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
            aria-describedby="height-help"
          />
          <p id="height-help" class="text-slate-500 text-xs mt-1">Altezza reale della persona</p>
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
            aria-describedby="mass-help"
          />
          <p id="mass-help" class="text-slate-500 text-xs mt-1">Peso della persona</p>
        </div>
        
        <button
          on:click={startAnalysisFromStep2}
          disabled={isCalibrating}
          class="btn-primary w-full"
          aria-label={isCalibrating ? 'Calibrazione e analisi in corso' : 'Avvia calibrazione e analisi'}
        >
          {isCalibrating ? 'Calibrazione e Analisi in corso...' : 'Avvia Analisi'}
        </button>
        
        {#if isCalibrating}
          <div class="bg-blue-500/10 border border-blue-500/50 rounded-lg p-3 sm:p-4" role="status" aria-live="polite">
            <p class="text-blue-400 text-sm">Sistema in calibrazione. Assicurati che la persona sia in posizione eretta nel frame.</p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Step 3: Analysis -->
    {#if currentStep === 3}
      <div class="space-y-4">
        <h3 class="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">3. Analisi Salto</h3>
        
        {#if !isAnalyzing}
          <button
            on:click={startAnalysis}
            class="btn-primary w-full"
            aria-label="Avvia analisi del salto"
          >
            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Avvia Analisi
          </button>
        {:else}
          <div class="bg-green-500/10 border border-green-500/50 rounded-lg p-3 sm:p-4" role="status" aria-live="polite">
            <p class="text-green-400 text-sm font-medium">Analisi in corso...</p>
            <p class="text-slate-400 text-xs mt-1">Il sistema sta elaborando il salto</p>
          </div>
        {/if}

        <!-- Real-time data display: visibile anche prima che partano i dati -->
        <div class="bg-slate-900/50 rounded-xl p-2.5 sm:p-3 md:p-4 border border-slate-700" role="region" aria-label="Dati in tempo reale">
          <h4 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2 sm:mb-3">Dati in Tempo Reale</h4>
          <div class="grid grid-cols-2 gap-1.5 sm:gap-2 md:gap-3" role="list">
            <div class="text-center" role="listitem">
              <p class="text-slate-400 text-[10px] sm:text-xs uppercase tracking-wide mb-0.5 sm:mb-1">Altezza Corrente</p>
              <p class="text-base sm:text-lg md:text-xl font-bold text-blue-400" aria-live="polite">{($appState.realtimeData?.current_height ?? 0)} cm</p>
            </div>
            <div class="text-center" role="listitem">
              <p class="text-slate-400 text-[10px] sm:text-xs uppercase tracking-wide mb-0.5 sm:mb-1">Altezza Max</p>
              <p class="text-base sm:text-lg md:text-xl font-bold text-green-400" aria-live="polite">{($appState.realtimeData?.max_height ?? 0)} cm</p>
            </div>
            <div class="text-center" role="listitem">
              <p class="text-slate-400 text-[10px] sm:text-xs uppercase tracking-wide mb-0.5 sm:mb-1">Velocità Decollo</p>
              <p class="text-base sm:text-lg md:text-xl font-bold text-purple-400" aria-live="polite">{($appState.realtimeData?.takeoff_velocity ?? 0)} cm/s</p>
            </div>
            <div class="text-center" role="listitem">
              <p class="text-slate-400 text-[10px] sm:text-xs uppercase tracking-wide mb-0.5 sm:mb-1">Potenza Est.</p>
              <p class="text-base sm:text-lg md:text-xl font-bold text-yellow-400" aria-live="polite">{($appState.realtimeData?.estimated_power ?? 0)} W</p>
            </div>
          </div>
        </div>

        {#if isAnalyzing}
          <div class="flex gap-2">
            {#if $appState.isPaused}
              <button
                on:click={resumeAnalysis}
                class="btn-secondary flex-1"
                aria-label="Riprendi analisi"
              >
                Riprendi
              </button>
            {:else}
              <button
                on:click={pauseAnalysis}
                class="btn-secondary flex-1"
                aria-label="Metti in pausa l'analisi"
              >
                Pausa
              </button>
            {/if}
            <button
              on:click={cancelAnalysis}
              class="btn-danger flex-1"
              aria-label="Annulla analisi"
            >
              Annulla
            </button>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Progress indicator -->
    <div class="mt-6 sm:mt-8 pt-4 sm:pt-6 border-t border-slate-700" role="progressbar" aria-valuenow={currentStep} aria-valuemin="1" aria-valuemax="3" aria-label="Progresso analisi">
      <div class="flex justify-between items-center mb-2">
        <span class="text-xs text-slate-400">Progresso</span>
        <span class="text-xs text-slate-400 font-medium">{currentStep}/3</span>
      </div>
      <div class="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
        <div
          class="bg-gradient-to-r from-purple-600 to-pink-600 h-2 rounded-full transition-all duration-300"
          style="width: {(currentStep / 3) * 100}%"
          aria-hidden="true"
        ></div>
      </div>
    </div>
  </div>
</div>

<style>
  .step-content::-webkit-scrollbar {
    width: 8px;
  }
  
  .step-content::-webkit-scrollbar-track {
    background: #1e293b;
    border-radius: 4px;
  }
  
  .step-content::-webkit-scrollbar-thumb {
    background: #475569;
    border-radius: 4px;
  }
  
  .step-content::-webkit-scrollbar-thumb:hover {
    background: #64748b;
  }
</style>