<script>
  import { onMount, onDestroy } from 'svelte';
  import { appState, updateVideoFrame } from './stores.js';
  
  export let analysisCompleted = false;
  let totalFrames = 0;
  let currentIndex = 0;
  let loading = false;
  let infoLoaded = false;
  let errorMsg = '';
  let frameFetchTimeout;
  let containerEl;
  let resizeObserver;
  let fullscreenHandler;
  let reflowTick = 0; // bump to force layout recalculation on resize/fullscreen toggle

  $: videoSrc = $appState.videoFrame ? `data:image/jpeg;base64,${$appState.videoFrame}` : null;
  let videoEl;

  async function loadVideoInfo() {
    try {
      const res = await fetch('http://localhost:5000/api/video/info');
      const data = await res.json();
      if (data && data.success) {
        totalFrames = data.total_frames || 0;
        infoLoaded = true;
      }
    } catch (e) {
      // ignore
    }
  }

  async function fetchFrameAt(index) {
    loading = true;
    errorMsg = '';
    try {
      const res = await fetch(`http://localhost:5000/api/video/frame_at?index=${index}`);
      const data = await res.json();
      if (data && data.success) {
        currentIndex = data.index;
        updateVideoFrame(data.frame);
      } else if (data && data.error) {
        errorMsg = data.error;
      }
    } catch (e) {
      errorMsg = 'Errore caricamento frame';
    } finally {
      loading = false;
    }
  }

  function prevFrame() {
    if (!analysisCompleted || totalFrames <= 0) return;
    const next = Math.max(0, currentIndex - 1);
    fetchFrameAt(next);
  }

  function nextFrame() {
    if (!analysisCompleted || totalFrames <= 0) return;
    const next = Math.min(totalFrames - 1, currentIndex + 1);
    fetchFrameAt(next);
  }

  function scheduleFetch(index) {
    if (!analysisCompleted || totalFrames <= 0) return;
    if (frameFetchTimeout) clearTimeout(frameFetchTimeout);
    frameFetchTimeout = setTimeout(() => {
      fetchFrameAt(index);
    }, 50);
  }

  $: (async () => {
    if (analysisCompleted && !infoLoaded) {
      await loadVideoInfo();
      if (totalFrames > 0) {
        await fetchFrameAt(currentIndex);
      }
    }
  })();

  function bumpReflow() {
    // Force Svelte to update bindings/layout-dependent children
    reflowTick++;
  }

  onMount(() => {
    if (typeof window !== 'undefined' && 'ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(() => {
        bumpReflow();
      });
      if (containerEl) resizeObserver.observe(containerEl);
    } else if (typeof window !== 'undefined') {
      window.addEventListener('resize', bumpReflow);
    }

    fullscreenHandler = () => {
      // run a few times to handle layout settling after exit
      bumpReflow();
      setTimeout(bumpReflow, 50);
      setTimeout(bumpReflow, 150);
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('fullscreenchange', fullscreenHandler);
      document.addEventListener('webkitfullscreenchange', fullscreenHandler);
      document.addEventListener('mozfullscreenchange', fullscreenHandler);
      document.addEventListener('MSFullscreenChange', fullscreenHandler);
    }
  });

  onDestroy(() => {
    if (resizeObserver && containerEl) resizeObserver.unobserve(containerEl);
    if (resizeObserver) resizeObserver.disconnect();
    if (typeof window !== 'undefined') window.removeEventListener('resize', bumpReflow);
    if (typeof document !== 'undefined' && fullscreenHandler) {
      document.removeEventListener('fullscreenchange', fullscreenHandler);
      document.removeEventListener('webkitfullscreenchange', fullscreenHandler);
      document.removeEventListener('mozfullscreenchange', fullscreenHandler);
      document.removeEventListener('MSFullscreenChange', fullscreenHandler);
    }
  });
</script>

<div class="video-container bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700" bind:this={containerEl}>
  <div class="video-header bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4">
    <h2 class="text-xl font-semibold text-white">Anteprima Video</h2>
  </div>
  
  <div class="video-content aspect-video bg-black flex items-center justify-center relative" data-reflow={reflowTick}>
    {#if analysisCompleted && $appState.localVideoUrl}
      <video
        bind:this={videoEl}
        src={$appState.localVideoUrl}
        controls
        class="w-full h-full object-contain"
      ></video>
    {:else if videoSrc}
      <img
        src={videoSrc}
        alt="Video frame"
        class="w-full h-full max-w-full max-h-full object-contain"
      />
      
      <!-- Recording indicator -->
      {#if $appState.isRecording}
        <div class="absolute top-4 right-4 flex items-center gap-2 bg-red-600 px-4 py-2 rounded-full">
          <div class="w-3 h-3 bg-white rounded-full animate-pulse"></div>
          <span class="text-white font-semibold text-sm">REC</span>
        </div>
      {/if}
      
      <!-- Analysis status -->
      {#if $appState.isAnalyzing}
        <div class="absolute top-4 left-4 bg-green-600 px-4 py-2 rounded-full">
          <span class="text-white font-semibold text-sm">ANALYZING</span>
        </div>
      {/if}
      
      <!-- Calibration status -->
      {#if $appState.isCalibrating}
        <div class="absolute top-4 left-4 bg-yellow-600 px-4 py-2 rounded-full">
          <span class="text-white font-semibold text-sm">CALIBRATING</span>
        </div>
      {/if}

      <!-- Playback slider (only after analysis) -->
      {#if analysisCompleted && !$appState.localVideoUrl}
        <div class="absolute bottom-4 left-1/2 -translate-x-1/2 bg-slate-900/80 backdrop-blur px-4 py-3 rounded-full border border-slate-700 flex items-center gap-4">
          <input
            type="range"
            min="0"
            max="{Math.max(totalFrames - 1, 0)}"
            bind:value={currentIndex}
            on:input={(e) => scheduleFetch(+e.target.value)}
            class="w-64 md:w-96 accent-purple-500"
          />
          <div class="text-slate-300 text-sm whitespace-nowrap">
            {`${currentIndex + 1} / ${Math.max(totalFrames, 0)}`}
          </div>
        </div>
        {#if errorMsg}
          <div class="absolute bottom-16 left-1/2 -translate-x-1/2 bg-red-600/80 text-white text-xs px-3 py-1 rounded">
            {errorMsg}
          </div>
        {/if}
      {/if}
    {:else}
      <div class="text-center p-8">
        <svg class="w-24 h-24 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <p class="text-slate-400 text-lg">Nessun video caricato</p>
        <p class="text-slate-500 text-sm mt-2">Carica o registra un video per iniziare</p>
      </div>
    {/if}
  </div>
  
</div>

<style>
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  
  .animate-pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
</style>