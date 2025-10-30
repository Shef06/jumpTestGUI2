<script>
  import { onMount, onDestroy } from 'svelte';
  import VideoPlayer from './lib/VideoPlayer.svelte';
  import StepHolder from './lib/StepHolder.svelte';
  import ResultsView from './lib/ResultsView.svelte';
  import { appState, updateVideoFrame, updateRealtimeData } from './lib/stores.js';

  let currentStep = 1;
  let showResults = false;
  let finalResults = null;
  let pollInterval;
  let videoColEl;
  let stepColEl;
  let resizeObserver;

  function syncStepHeight() {
    if (!videoColEl || !stepColEl) return;
    const isWide = typeof window !== 'undefined' ? window.innerWidth >= 1024 : true; // lg breakpoint
    if ((currentStep === 3 && !showResults && isWide) || (showResults && isWide)) {
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
    // Initial sync
    setTimeout(syncStepHeight, 0);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
    if (resizeObserver && videoColEl) resizeObserver.unobserve(videoColEl);
    if (resizeObserver) resizeObserver.disconnect();
    if (typeof window !== 'undefined') window.removeEventListener('resize', syncStepHeight);
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

  function handleReset() {
    showResults = false;
    finalResults = null;
    currentStep = 1;
    appState.set({
      isAnalyzing: false,
      isRecording: false,
      isCalibrating: false,
      isPaused: false,
      videoFrame: null,
      realtimeData: {},
      trajectoryData: [],
      velocityData: []
    });
  }

  function goToPreviousStep() {
    if (currentStep > 1) {
      currentStep--;
      syncStepHeight();
      // Reset state when going back
      if (currentStep === 1) {
        appState.set({
          isAnalyzing: false,
          isRecording: false,
          isCalibrating: false,
          isPaused: false,
          videoFrame: null,
          realtimeData: {},
          trajectoryData: [],
          velocityData: []
        });
      }
    }
  }

  $: syncStepHeight();
</script>

<main class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
  <!-- Header -->
  <header class="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700">
    <div class="container mx-auto px-6 py-6">
      <h1 class="text-4xl font-bold text-white tracking-tight">
        Jump Analyzer Pro
      </h1>
    </div>
  </header>

  <!-- Main Content -->
  <div class="container mx-auto px-6 py-8">
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
  :global(body) {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
</style>