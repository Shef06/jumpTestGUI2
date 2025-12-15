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
  
  // Polling ottimizzato
  let pollRate = 150;
  let consecutiveErrors = 0;
  let maxPollRate = 500;

  async function adaptivePoll() {
    if (!$appState.isAnalyzing && !$appState.isRecording && !$appState.isCalibrating) return;

    try {
      if ($appState.isAnalyzing || $appState.isRecording || $appState.isCalibrating) {
        const frameRes = await fetch(`${getBackendUrl()}/api/video/frame`, { signal: AbortSignal.timeout(1000) });
        if (frameRes.ok) {
          const frameData = await frameRes.json();
          if (frameData.success && frameData.frame) updateVideoFrame(frameData.frame);
        }
      }

      if ($appState.isAnalyzing) {
        const dataRes = await fetch(`${getBackendUrl()}/api/analysis/data`, { signal: AbortSignal.timeout(1000) });
        if (dataRes.ok) {
          const data = await dataRes.json();
          if (data.realtime) updateRealtimeData(data.realtime, data.trajectory, data.velocity);
        }
      }
      if (consecutiveErrors > 0) {
        consecutiveErrors = Math.max(0, consecutiveErrors - 1);
        pollRate = Math.max(150, pollRate - 50);
      }
    } catch (e) {
      consecutiveErrors++;
      if (consecutiveErrors > 3) pollRate = Math.min(maxPollRate, pollRate + 50);
    }
  }

  onMount(() => {
    pollInterval = setInterval(adaptivePoll, pollRate);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

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
    } else if (step === 3) {
      finalResults = data;
      showResults = true;
    }
  }

  async function stopProcessesSafely() {
    const promises = [];
    if ($appState.isAnalyzing) promises.push(fetch(`${getBackendUrl()}/api/analysis/stop`, { method: 'POST' }).catch(() => {}));
    if ($appState.isRecording) promises.push(fetch(`${getBackendUrl()}/api/recording/stop`, { method: 'POST' }).catch(() => {}));
    await Promise.all(promises);
  }

  async function cancelAndExit() {
    await stopProcessesSafely();
    try { $appState.previewStream?.getTracks()?.forEach(t => t.stop()); } catch (e) {}
    clearPreviewStream();
    
    // Reset totale (chiusura app)
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

  // Modificata per accettare keepVideo
  function handleReset(keepVideo = false) {
    showResults = false;
    finalResults = null;
    currentStep = 1;
    consecutiveErrors = 0;
    pollRate = 150;
    
    appState.update(s => ({
      isAnalyzing: false,
      isRecording: false,
      isCalibrating: false,
      isPaused: false,
      isCameraPreview: false,
      // Se keepVideo è true, preserva inputMode (es. 'upload') e localVideoUrl
      inputMode: keepVideo ? s.inputMode : 'none',
      videoFrame: null,
      realtimeData: {},
      trajectoryData: [],
      velocityData: [],
      localVideoUrl: keepVideo ? s.localVideoUrl : null
    }));
  }

  async function goToPreviousStep() {
    if (currentStep > 1) {
      await stopProcessesSafely();
      currentStep--;
    }
  }

  async function handleCancelToStep1() {
    await stopProcessesSafely();
    currentStep = 1;
    // Passiamo true per mantenere il video caricato
    handleReset(true);
  }
</script>

<main class="h-screen bg-slate-950 text-slate-200 font-sans flex flex-col overflow-hidden selection:bg-indigo-500/30">
  <!-- Navbar -->
  <header class="h-14 bg-slate-900 border-b border-slate-800 flex items-center px-6 shrink-0 justify-between shadow-sm z-20">
    <div class="font-bold text-lg text-white tracking-tight flex items-center gap-2">
      <div class="bg-indigo-600 p-1.5 rounded-md shadow-lg shadow-indigo-500/20">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-white"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </div>
      JumpAnalyzer <span class="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400 font-medium border border-slate-700">PRO BETA</span>
    </div>
    
    <div class="flex items-center gap-4">
       <button 
          on:click={cancelAndExit} 
          class="text-xs font-medium text-red-400 hover:text-red-300 border border-red-900/30 bg-red-900/10 px-3 py-1.5 rounded hover:bg-red-900/20 transition-colors"
       >
          Chiudi
       </button>
       <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 border-2 border-slate-800 cursor-pointer"></div>
    </div>
  </header>

  <!-- Main Grid -->
  <div class="flex-1 p-4 grid grid-cols-1 lg:grid-cols-12 gap-4 overflow-hidden max-w-[1800px] mx-auto w-full">
    
    <!-- COLONNA SINISTRA: VIDEO (8/12) -->
    <div class="lg:col-span-8 flex flex-col h-full overflow-hidden">
      <VideoPlayer analysisCompleted={showResults} />
    </div>

    <!-- COLONNA DESTRA: SIDEBAR (4/12) -->
    <div class="lg:col-span-4 flex flex-col h-full overflow-hidden">
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
          on:exitNoSave={handleReset}
          on:uploadComplete={handleReset}
        />
      {/if}
    </div>
  </div>
</main>

<style>
  :global(body) {
    margin: 0;
    background-color: #020617; /* slate-950 */
  }
</style>