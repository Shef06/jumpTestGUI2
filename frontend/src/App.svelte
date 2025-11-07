<script>
  import { onMount, onDestroy } from 'svelte';
  import VideoPlayer from './lib/VideoPlayer.svelte';
  import StepHolder from './lib/StepHolder.svelte';
  import ResultsView from './lib/ResultsView.svelte';
  import { appState, updateVideoFrame, updateRealtimeData, clearPreviewStream } from './lib/stores.js';

  let currentStep = 1;
  let showResults = false;
  let finalResults = null;
  let pollInterval;
  let videoColEl;
  let stepColEl;
  let resizeObserver;
  let fullscreenHandler;

  function syncStepHeight() {
    if (!videoColEl || !stepColEl) return;
    const isWide = typeof window !== 'undefined' ? window.innerWidth >= 1024 : true; // lg breakpoint
    if (isWide) {
      const h = videoColEl.clientHeight;
      stepColEl.style.height = h ? `${h}px` : '';
    } else {
      stepColEl.style.height = '';
    }
  }

  onMount(() => {
    // Polling per aggiornamenti frame e dati
    pollInterval = setInterval(async () => {
      if ($appState.isAnalyzing || $appState.isRecording || $appState.isCalibrating) {
        // Aggiorna frame video
        try {
          const frameRes = await fetch('http://localhost:5000/api/video/frame');
          const frameData = await frameRes.json();
          if (frameData.success && frameData.frame) {
            updateVideoFrame(frameData.frame);
          }
        } catch (e) {}

        // Aggiorna dati analisi
        if ($appState.isAnalyzing) {
          try {
            const dataRes = await fetch('http://localhost:5000/api/analysis/data');
            const data = await dataRes.json();
            if (data.realtime) {
              updateRealtimeData(data.realtime, data.trajectory, data.velocity);
            }
          } catch (e) {}
        }
      }
    }, 100);

    // Observe video column size to sync step height
    if (window && 'ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(() => {
        syncStepHeight();
      });
      if (videoColEl) resizeObserver.observe(videoColEl);
    } else {
      // Fallback on window resize
      window.addEventListener('resize', syncStepHeight);
    }
    // Also handle fullscreen toggles (F11) which may not always fire ResizeObserver immediately
    fullscreenHandler = () => {
      // Run multiple times to account for layout settling
      syncStepHeight();
      setTimeout(syncStepHeight, 50);
      setTimeout(syncStepHeight, 150);
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('fullscreenchange', fullscreenHandler);
      document.addEventListener('webkitfullscreenchange', fullscreenHandler);
      document.addEventListener('mozfullscreenchange', fullscreenHandler);
      document.addEventListener('MSFullscreenChange', fullscreenHandler);
    }
    // Initial sync
    setTimeout(syncStepHeight, 0);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
    if (resizeObserver && videoColEl) resizeObserver.unobserve(videoColEl);
    if (resizeObserver) resizeObserver.disconnect();
    if (typeof window !== 'undefined') window.removeEventListener('resize', syncStepHeight);
    if (typeof document !== 'undefined' && fullscreenHandler) {
      document.removeEventListener('fullscreenchange', fullscreenHandler);
      document.removeEventListener('webkitfullscreenchange', fullscreenHandler);
      document.removeEventListener('mozfullscreenchange', fullscreenHandler);
      document.removeEventListener('MSFullscreenChange', fullscreenHandler);
    }
  });

  function handleStepComplete(event) {
    const { step, data } = event.detail;
    
    if (step === 1) {
      // Video caricato o registrato
      currentStep = 2;
    } else if (step === 2) {
      // Calibrazione completata
      currentStep = 3;
      syncStepHeight();
    } else if (step === 3) {
      // Analisi completata
      finalResults = data;
      showResults = true;
      syncStepHeight();
    }
  }

  async function stopAnalysisSafely() {
    try {
      await fetch('http://localhost:5000/api/analysis/stop', { method: 'POST' });
    } catch (e) {}
  }

  async function stopRecordingSafely() {
    try {
      await fetch('http://localhost:5000/api/recording/stop', { method: 'POST' });
    } catch (e) {}
  }

  async function cancelAndExit() {
    try { await fetch('http://localhost:5000/api/analysis/stop', { method: 'POST' }); } catch (e) {}
    try { await fetch('http://localhost:5000/api/recording/stop', { method: 'POST' }); } catch (e) {}
    try { $appState.previewStream?.getTracks()?.forEach(t => t.stop()); } catch (e) {}
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
      // Step-specific side effects BEFORE changing step
      if (currentStep === 2) {
        // Going 2 -> 1: kill session-like state and stop any fetching
        await stopAnalysisSafely();
        await stopRecordingSafely();
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
        // Going 3 -> 2: stop analysis playback and reset step-2 related data
        await stopAnalysisSafely();
        appState.update((s) => ({
          ...s,
          isAnalyzing: false,
          isPaused: false,
          isCameraPreview: s.isCameraPreview,
          realtimeData: {},
          trajectoryData: [],
        velocityData: [],
        localVideoUrl: s.localVideoUrl // keep in step back 3->2
        }));
      }

      currentStep--;
      syncStepHeight();
    }
  }

  async function handleCancelToStep1() {
    await stopAnalysisSafely();
    await stopRecordingSafely();
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

  $: syncStepHeight();
</script>

<main class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
  <!-- Header -->
  <header class="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700">
    <div class="max-w-[1400px] mx-auto px-6 py-6">
      <div class="flex items-center justify-between">
        <h1 class="text-4xl font-bold text-white tracking-tight">Jump Analyzer Pro</h1>
        <button on:click={cancelAndExit} class="bg-red-600 hover:bg-red-700 text-white px-5 py-2 rounded-lg font-semibold border border-red-500/50 shadow-md">
          Annulla Analisi
        </button>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <div class="max-w-[1400px] mx-auto px-6 py-8">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Video Player (2/3 width on large screens) -->
      <div class="lg:col-span-2" bind:this={videoColEl}>
        <VideoPlayer analysisCompleted={showResults} />
      </div>

      <!-- Step Holder (1/3 width on large screens) -->
      <div class="lg:col-span-1" bind:this={stepColEl}>
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
    background-color: #0f172a; /* slate-900 */
  }

  :global(#app) {
    min-height: 100%;
    background-color: #0f172a; /* slate-900 */
  }
  :global(body) {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
</style>