<script>
  import { onMount, onDestroy } from 'svelte';
  import { appState, updateVideoFrame } from './stores.js';
  import { getBackendUrl } from './api.js';
  
  export let analysisCompleted = false;
  let totalFrames = 0;
  let currentIndex = 0;
  let loading = false;
  let infoLoaded = false;
  let errorMsg = '';
  let frameFetchTimeout;
  let containerEl;
  let resizeObserver;
  let videoEl;

  $: videoSrc = $appState.videoFrame ? `data:image/jpeg;base64,${$appState.videoFrame}` : null;

  async function loadVideoInfo() {
    try {
      const res = await fetch(`${getBackendUrl()}/api/video/info`);
      const data = await res.json();
      if (data && data.success) {
        totalFrames = data.total_frames || 0;
        infoLoaded = true;
      }
    } catch (e) {}
  }

  async function fetchFrameAt(index) {
    loading = true;
    try {
      const res = await fetch(`${getBackendUrl()}/api/video/frame_at?index=${index}`);
      const data = await res.json();
      if (data && data.success) {
        currentIndex = data.index;
        updateVideoFrame(data.frame);
      } else if (data && data.error) errorMsg = data.error;
    } catch (e) { errorMsg = 'Errore caricamento frame'; } 
    finally { loading = false; }
  }

  function scheduleFetch(index) {
    if (!analysisCompleted || totalFrames <= 0) return;
    if (frameFetchTimeout) clearTimeout(frameFetchTimeout);
    frameFetchTimeout = setTimeout(() => fetchFrameAt(index), 50);
  }

  $: if (analysisCompleted && !infoLoaded) {
      loadVideoInfo().then(() => { if (totalFrames > 0) fetchFrameAt(currentIndex); });
  }

  onMount(() => {
    if ($appState.isCameraPreview && $appState.previewStream && videoEl) {
      try { videoEl.srcObject = $appState.previewStream; } catch (_) {}
    }
  });

  $: if ($appState.isCameraPreview && $appState.previewStream && videoEl) {
    try { videoEl.srcObject = $appState.previewStream; } catch (e) {}
  }
</script>

<div class="bg-black rounded-2xl overflow-hidden border border-slate-800 relative shadow-2xl ring-1 ring-white/5 group h-full flex flex-col" bind:this={containerEl}>
  <div class="absolute top-0 left-0 right-0 p-4 z-10 bg-gradient-to-b from-black/90 via-black/40 to-transparent flex justify-between items-start pointer-events-none">
     <div class="flex flex-col">
         <span class="text-white font-medium text-sm drop-shadow-md">Analisi Biomeccanica</span>
         <span class="text-[10px] font-mono text-slate-300 opacity-80">
            {#if analysisCompleted}VIDEO ANALYZED{:else if $appState.isCameraPreview}LIVE PREVIEW{:else}SOURCE MEDIA{/if}
         </span>
     </div>
  </div>

  <div class="flex-1 bg-black flex items-center justify-center relative overflow-hidden">
    {#if $appState.isCameraPreview && $appState.previewStream}
      <video bind:this={videoEl} autoplay playsinline muted class="w-full h-full object-contain"></video>
    {:else if analysisCompleted && $appState.localVideoUrl}
      <video bind:this={videoEl} src={$appState.localVideoUrl} controls class="w-full h-full object-contain"></video>
    {:else if videoSrc}
      <img src={videoSrc} alt="Video frame" class="w-full h-full object-contain" />
      {#if $appState.isRecording}
        <div class="absolute top-4 right-4 flex items-center gap-2 bg-red-600 px-3 py-1 rounded-full shadow-lg animate-pulse">
          <div class="w-2 h-2 bg-white rounded-full"></div><span class="text-white text-xs font-bold">REC</span>
        </div>
      {/if}
      {#if $appState.isAnalyzing}
        <div class="absolute bottom-4 left-4 bg-green-600/90 backdrop-blur px-3 py-1 rounded-lg border border-green-500/50">
          <span class="text-white text-xs font-bold">ANALYZING...</span>
        </div>
      {/if}
    {:else}
       <div class="text-center p-8 opacity-50">
          <svg class="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
          <p class="text-slate-400 text-sm">Nessun video caricato</p>
       </div>
    {/if}
  </div>

  {#if analysisCompleted && !$appState.localVideoUrl && totalFrames > 0}
    <div class="h-16 bg-slate-900/95 border-t border-slate-800/80 backdrop-blur-sm px-6 flex items-center gap-6 shrink-0">
        <div class="flex-1 flex flex-col gap-1.5 justify-center">
            <div class="flex justify-between text-[10px] font-mono text-slate-400 px-0.5">
                <span>Frame {currentIndex}</span>
                <span>{totalFrames}</span>
            </div>
            <input
                type="range"
                min="0"
                max="{Math.max(totalFrames - 1, 0)}"
                bind:value={currentIndex}
                on:input={(e) => scheduleFetch(+e.target.value)}
                class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
        </div>
    </div>
  {/if}
</div>