<script>
  import { onMount, onDestroy } from 'svelte';
  import VideoPlayer from './lib/VideoPlayer.svelte';
  import StepHolder from './lib/StepHolder.svelte';
  import ResultsView from './lib/ResultsView.svelte';
  import { appState, updateVideoFrame, updateRealtimeData, clearPreviewStream } from './lib/stores.js';
  import { getBackendUrl } from './lib/api.js';

  let currentStep = 1;
  let showResults = false;
  let finalResults = null;
  let pollInterval;
  let videoColEl;
  let stepColEl;
  let resizeObserver;
  let fullscreenHandler;
  let resizeDebounce;

  // Polling ottimizzato con rate adaptativo
  let pollRate = 150; // Aumentato da 100ms a 150ms
  let consecutiveErrors = 0;
  let maxPollRate = 500;

  function syncStepHeight() {
    if (!videoColEl || !stepColEl) return;
    const isWide = typeof window !== 'undefined' ? window.innerWidth >= 1024 : true;
    if (isWide) {
      const h = videoColEl.clientHeight;
      stepColEl.style.height = h ? `${h}px` : '';
    } else {
      stepColEl.style.height = '';
    }
  }

  function debouncedSyncHeight() {
    if (resizeDebounce) clearTimeout(resizeDebounce);
    resizeDebounce = setTimeout(syncStepHeight, 100);
  }

  async function adaptivePoll() {
    if (!$appState.isAnalyzing && !$appState.isRecording && !$appState.isCalibrating) {
      // Non serve polling se non ci sono processi attivi
      return;
    }

    try {
      // Fetch frame solo se necessario
      if ($appState.isAnalyzing || $appState.isRecording || $appState.isCalibrating) {
        const frameRes = await fetch(`${getBackendUrl()}/api/video/frame`, {
          signal: AbortSignal.timeout(1000) // Timeout 1s
        });
        
        if (frameRes.ok) {
          const frameData = await frameRes.json();
          if (frameData.success && frameData.frame) {
            updateVideoFrame(frameData.frame);
          }
        }
      }

      // Fetch dati analisi solo durante analisi
      if ($appState.isAnalyzing) {
        const dataRes = await fetch(`${getBackendUrl()}/api/analysis/data`, {
          signal: AbortSignal.timeout(1000)
        });
        
        if (dataRes.ok) {
          const data = await dataRes.json();
          if (data.realtime) {
            updateRealtimeData(data.realtime, data.trajectory, data.velocity);
          }
        }
      }

      // Success: reduce poll rate se era stato aumentato
      if (consecutiveErrors > 0) {
        consecutiveErrors = Math.max(0, consecutiveErrors - 1);
        pollRate = Math.max(150, pollRate - 50);
      }

    } catch (e) {
      // Error: increase poll rate per ridurre carico
      consecutiveErrors++;
      if (consecutiveErrors > 3) {
        pollRate = Math.min(maxPollRate, pollRate + 50);
      }
    }
  }

  onMount(() => {
    // Polling con rate adaptativo
    pollInterval = setInterval(adaptivePoll, pollRate);

    // Observe video column size
    if (window && 'ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(debouncedSyncHeight);
      if (videoColEl) resizeObserver.observe(videoColEl);
    } else {
      window?.addEventListener('resize', debouncedSyncHeight);
    }

    // Fullscreen handler con debounce
    fullscreenHandler = () => {
      debouncedSyncHeight();
      setTimeout(syncStepHeight, 150);
    };
    
    if (typeof document !== 'undefined') {
      document.addEventListener('fullscreenchange', fullscreenHandler);
      document.addEventListener('webkitfullscreenchange', fullscreenHandler);
      document.addEventListener('mozfullscreenchange', fullscreenHandler);
      document.addEventListener('MSFullscreenChange', fullscreenHandler);
    }

    setTimeout(syncStepHeight, 0);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
    if (resizeDebounce) clearTimeout(resizeDebounce);
    if (resizeObserver && videoColEl) resizeObserver.unobserve(videoColEl);
    if (resizeObserver) resizeObserver.disconnect();
    if (typeof window !== 'undefined') window.removeEventListener('resize', debouncedSyncHeight);
    if (typeof document !== 'undefined' && fullscreenHandler) {
      document.removeEventListener('fullscreenchange', fullscreenHandler);
      document.removeEventListener('webkitfullscreenchange', fullscreenHandler);
      document.removeEventListener('mozfullscreenchange', fullscreenHandler);
      document.removeEventListener('MSFullscreenChange', fullscreenHandler);
    }
  });

  // Update poll rate quando cambia
  $: if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = setInterval(adaptivePoll, pollRate);
  }

  function handleStepComplete(event) {
    const { step, data } = event.detail;
    
    if (step === 1) {
      currentStep = 2;
    } else if (step === 2) {
      currentStep = 3;
      syncStepHeight();
    } else if (step === 3) {
      finalResults = data;
      showResults = true;
      syncStepHeight();
    }
  }

  async function stopProcessesSafely() {
    const promises = [];
    
    if ($appState.isAnalyzing) {
      promises.push(
        fetch(`${getBackendUrl()}/api/analysis/stop`, { method: 'POST' })
          .catch(() => {})
      );
    }
    
    if ($appState.isRecording) {
      promises.push(
        fetch(`${getBackendUrl()}/api/recording/stop`, { method: 'POST' })
          .catch(() => {})
      );
    }

    await Promise.all(promises);
  }

  async function cancelAndExit() {
    await stopProcessesSafely();
    
    try { 
      $appState.previewStream?.getTracks()?.forEach(t => t.stop()); 
    } catch (e) {}
    
    clearPreviewStream();
    
    appState.set({
      isAnalyzing: false,
      isRecording: false,
      isCalibrating: false,
      isPaused: false,
      isCameraPreview: false,
      inputMode: 'none',
      videoFrame: null,
      realtimeData: {},
      trajectoryData: [],
      velocityData: [],
      localVideoUrl: null
    });
    
    try { window.close(); } catch (e) {}
  }

  function handleReset() {
    showResults = false;
    finalResults = null;
    currentStep = 1;
    consecutiveErrors = 0;
    pollRate = 150;
    
    appState.set({
      isAnalyzing: false,
      isRecording: false,
      isCalibrating: false,
      isPaused: false,
      isCameraPreview: false,
      inputMode: 'none',
      videoFrame: null,
      realtimeData: {},
      trajectoryData: [],
      velocityData: [],
      localVideoUrl: null
    });
  }

  async function goToPreviousStep() {
    if (currentStep > 1) {
      if (currentStep === 2) {
        await stopProcessesSafely();
        appState.set({
          isAnalyzing: false,
          isRecording: false,
          isCalibrating: false,
          isPaused: false,
          isCameraPreview: false,
          inputMode: 'none',
          videoFrame: null,
          realtimeData: {},
          trajectoryData: [],
          velocityData: [],
          localVideoUrl: null
        });
      } else if (currentStep === 3) {
        await stopProcessesSafely();
        appState.update((s) => ({
          ...s,
          isAnalyzing: false,
          isPaused: false,
          isCameraPreview: s.isCameraPreview,
          realtimeData: {},
          trajectoryData: [],
          velocityData: [],
          localVideoUrl: s.localVideoUrl
        }));
      }

      currentStep--;
      syncStepHeight();
    }
  }

  async function handleCancelToStep1() {
    await stopProcessesSafely();
    currentStep = 1;
    
    appState.set({
      isAnalyzing: false,
      isRecording: false,
      isCalibrating: false,
      isPaused: false,
      isCameraPreview: false,
      inputMode: 'none',
      videoFrame: null,
      realtimeData: {},
      trajectoryData: [],
      velocityData: [],
      localVideoUrl: null
    });
    
    syncStepHeight();
  }
</script>

<main class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" role="main" aria-label="Jump Analyzer Pro - Analisi salto">
  <header class="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700" role="banner">
    <div class="max-w-[1400px] mx-auto px-4 sm:px-6 py-4 sm:py-6">
      <div class="flex items-center justify-between gap-4">
        <h1 class="text-2xl sm:text-3xl lg:text-4xl font-bold text-white tracking-tight">Jump Analyzer Pro</h1>
        <button 
          on:click={cancelAndExit} 
          class="bg-red-600 hover:bg-red-700 focus:bg-red-700 text-white px-4 sm:px-5 py-2 rounded-lg font-semibold border border-red-500/50 shadow-md transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-slate-800"
          aria-label="Chiudi analisi e esci dall'applicazione"
        >
          Chiudi Analisi
        </button>
      </div>
    </div>
  </header>

  <div class="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
      <div class="lg:col-span-2" bind:this={videoColEl} aria-label="Anteprima video">
        <VideoPlayer analysisCompleted={showResults} />
      </div>

      <div class="lg:col-span-1" bind:this={stepColEl} aria-label="Pannello controllo">
        {#if !showResults}
          <StepHolder 
            {currentStep} 
            on:stepComplete={handleStepComplete}
            on:goBack={goToPreviousStep}
            on:cancelToStep1={handleCancelToStep1}
          />
        {:else}
          <ResultsView 
            results={finalResults}
            on:reset={handleReset}
          />
        {/if}
      </div>
    </div>
  </div>
</main>

<style>
  :global(html, body) {
    height: 100%;
    background-color: #0f172a;
  }

  :global(#app) {
    min-height: 100%;
    background-color: #0f172a;
  }
  
  :global(body) {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
</style>