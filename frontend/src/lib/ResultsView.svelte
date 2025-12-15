<script>
  import { createEventDispatcher } from 'svelte';
  import { appState, sessionStore, addJumpToSession } from './stores.js';
  import { getBackendUrl } from './api.js';
  import SummaryView from './SummaryView.svelte';
  
  export let results;
  
  const dispatch = createEventDispatcher();
  
  // Stato Interfaccia
  let view = 'analysis'; // 'analysis' | 'summary'
  let activeTab = 'metrics'; // 'metrics' | 'charts'
  let activeGraph = 'trajectory'; // 'trajectory' | 'velocity' | 'combined'
  let isSaving = false;
  let saveMessage = '';
  let lastAddedJumpHash = null; // Traccia l'ultimo salto aggiunto per evitare duplicati
  
  // Aggiungi il salto alla sessione quando i risultati arrivano (solo se non siamo in summary)
  $: if (results && view === 'analysis') {
    // Crea un hash univoco per questo salto basato sui dati chiave
    const jumpHash = `${results.max_height || 0}_${results.flight_time || 0}_${results.timestamp || Date.now()}`;
    
    // Se questo è lo stesso salto che abbiamo appena aggiunto, ignora
    if (jumpHash !== lastAddedJumpHash) {
      const currentJumps = $sessionStore.jumps;
      // Verifica se questo salto è già nella sessione (confronta timestamp o dati chiave)
      const jumpExists = currentJumps.some(j => {
        // Se hanno lo stesso ID, sono lo stesso salto
        if (j.id && results.id && j.id === results.id) return true;
        // Altrimenti confronta dati chiave (altezza, tempo volo, timestamp se disponibile)
        const jHash = `${j.max_height || 0}_${j.flight_time || 0}_${j.timestamp || 0}`;
        return jHash === jumpHash || (
          j.max_height === results.max_height && 
          j.flight_time === results.flight_time &&
          Math.abs((j.timestamp || 0) - (results.timestamp || Date.now())) < 1000
        );
      });
      
      if (!jumpExists) {
        addJumpToSession(results);
        lastAddedJumpHash = jumpHash;
      } else {
        // Se il salto esiste già, aggiorna l'hash per evitare controlli futuri
        lastAddedJumpHash = jumpHash;
      }
    }
  }
  
  // Canvas ref
  let canvasRef;
  
  // Dati processati
  let derivedVelocityData = [];
  let phaseTimes = null;
  
  // Stili Grafici
  const GRID_STEPS = 5;
  const TRAJECTORY_STYLE = {
    background: '#020617', // slate-950
    grid: '#1e293b',      // slate-800
    axis: '#334155',      // slate-700
    line: '#4ade80',      // emerald-400
    lineShadow: 'rgba(74, 222, 128, 0.35)',
    fill: 'rgba(74, 222, 128, 0.1)',
    label: '#94a3b8',     // slate-400
    zero: '#64748b'
  };
  const VELOCITY_STYLE = {
    background: '#020617',
    grid: '#1e293b',
    axis: '#334155',
    line: '#a78bfa',      // purple-400
    lineShadow: 'rgba(167, 139, 250, 0.35)',
    fillAbove: 'rgba(167, 139, 250, 0.15)',
    fillBelow: 'rgba(148, 163, 184, 0.1)',
    label: '#a78bfa',
    zero: '#64748b'
  };

  // Inizializza Dati
  $: if (results) {
    derivedVelocityData = results.velocity || [];
    phaseTimes = results.phase_times || null;
    if (results.trajectory) {
      $appState.trajectoryData = results.trajectory;
    }
  }

  // Reattività per ridisegnare il grafico
  $: if (activeTab === 'charts' && canvasRef) {
    setTimeout(() => {
      if(activeGraph === 'trajectory') drawTrajectoryChart();
      else if(activeGraph === 'velocity') drawVelocityChart();
      else if(activeGraph === 'combined') drawCombinedChart();
    }, 50);
  }

  // Funzioni di Disegno
  function clearCanvas(ctx, width, height, background) {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);
  }

  function drawTrajectoryChart() {
    if (!canvasRef || $appState.trajectoryData.length === 0) return;
    
    const dpr = window.devicePixelRatio || 1;
    const rect = canvasRef.getBoundingClientRect();
    canvasRef.width = rect.width * dpr;
    canvasRef.height = rect.height * dpr;
    
    const ctx = canvasRef.getContext('2d');
    ctx.scale(dpr, dpr);
    
    const width = rect.width;
    const height = rect.height;
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;

    clearCanvas(ctx, width, height, TRAJECTORY_STYLE.background);

    const data = $appState.trajectoryData;
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxY = Math.max(...data.map(d => d.y));
    const minY = Math.min(...data.map(d => d.y));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaY = maxY === minY ? 1 : (maxY - minY);

    drawGrid(ctx, { padding, width, height, chartWidth, chartHeight, minT, deltaT, minY, deltaY, style: TRAJECTORY_STYLE, xFormatter: v => v.toFixed(2), yFormatter: v => v.toFixed(0) });

    if (phaseTimes) drawPhasesBackground(ctx, phaseTimes, minT, deltaT, padding, chartWidth, chartHeight);

    ctx.lineWidth = 3;
    ctx.strokeStyle = TRAJECTORY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = TRAJECTORY_STYLE.lineShadow;
    ctx.shadowBlur = 10;
    
    ctx.beginPath();
    data.forEach((point, i) => {
      const x = padding + ((point.t - minT) / deltaT) * chartWidth;
      const y = height - padding - ((point.y - minY) / deltaY) * chartHeight;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    if (phaseTimes) drawPhaseMarkers(ctx, phaseTimes, minT, deltaT, padding, chartWidth, height);
  }

  function drawVelocityChart() {
    if (!canvasRef || derivedVelocityData.length === 0) return;
    
    const dpr = window.devicePixelRatio || 1;
    const rect = canvasRef.getBoundingClientRect();
    canvasRef.width = rect.width * dpr;
    canvasRef.height = rect.height * dpr;
    const ctx = canvasRef.getContext('2d');
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;

    clearCanvas(ctx, width, height, VELOCITY_STYLE.background);

    const data = derivedVelocityData;
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxV = Math.max(...data.map(d => d.v));
    const minV = Math.min(...data.map(d => d.v));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaV = maxV === minV ? (Math.abs(maxV) || 1) : (maxV - minV);

    drawGrid(ctx, { padding, width, height, chartWidth, chartHeight, minT, deltaT, minY: minV, deltaY: deltaV, style: VELOCITY_STYLE, xFormatter: v => v.toFixed(2), yFormatter: v => v.toFixed(0) });
    
    if (minV <= 0 && maxV >= 0) {
      const zeroY = height - padding - ((0 - minV) / deltaV) * chartHeight;
      ctx.strokeStyle = VELOCITY_STYLE.zero;
      ctx.setLineDash([5, 5]);
      ctx.beginPath(); ctx.moveTo(padding, zeroY); ctx.lineTo(width - padding, zeroY); ctx.stroke(); ctx.setLineDash([]);
    }

    if (phaseTimes) drawPhasesBackground(ctx, phaseTimes, minT, deltaT, padding, chartWidth, chartHeight);

    ctx.lineWidth = 3;
    ctx.strokeStyle = VELOCITY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.shadowColor = VELOCITY_STYLE.lineShadow;
    ctx.shadowBlur = 10;

    ctx.beginPath();
    data.forEach((point, i) => {
      const x = padding + ((point.t - minT) / deltaT) * chartWidth;
      const y = height - padding - ((point.v - minV) / deltaV) * chartHeight;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    if (phaseTimes) drawPhaseMarkers(ctx, phaseTimes, minT, deltaT, padding, chartWidth, height);
  }

  function drawCombinedChart() {
    if (!canvasRef) return;
    const tData = $appState.trajectoryData;
    const vData = derivedVelocityData;
    
    if (tData.length === 0 || vData.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvasRef.getBoundingClientRect();
    canvasRef.width = rect.width * dpr;
    canvasRef.height = rect.height * dpr;
    const ctx = canvasRef.getContext('2d');
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;

    clearCanvas(ctx, width, height, TRAJECTORY_STYLE.background);

    // --- NORMALIZZAZIONE & ALLINEAMENTO ZERI ---

    // 1. Normalizza altezza (Spostamento relativo da 0)
    // Così t=0 parte da y=0, come la velocità
    const startH = tData[0]?.y || 0;
    const shiftedTData = tData.map(d => ({...d, y: d.y - startH}));

    // 2. Calcola i range estesi (incluso 0)
    let maxT = Math.max(0, ...shiftedTData.map(d => d.y));
    let minT = Math.min(0, ...shiftedTData.map(d => d.y));
    let maxV = Math.max(0, ...vData.map(d => d.v));
    let minV = Math.min(0, ...vData.map(d => d.v));

    // 3. Calcola quanto spazio serve "sotto lo zero" per ciascun grafico
    // ratio = |min| / (max - min)
    const rangeT = maxT - minT || 1;
    const rangeV = maxV - minV || 1;
    const ratioBelowT = Math.abs(minT) / rangeT;
    const ratioBelowV = Math.abs(minV) / rangeV;

    // 4. Trova il rapporto dominante (chi ha più bisogno di spazio sotto lo zero)
    const targetRatioBelow = Math.max(ratioBelowT, ratioBelowV);

    // 5. Ricalcola i Minimi fittizi per allineare gli Zeri allo stesso livello Y
    // Formula inversa: min = -(targetRatio * max) / (1 - targetRatio)
    let alignMinT = minT;
    let alignMaxT = maxT;
    let alignMinV = minV;
    let alignMaxV = maxV;

    // Se la traiettoria ha meno negativo della velocità, estendi il suo minimo
    if (ratioBelowT < targetRatioBelow) {
        alignMinT = - (targetRatioBelow * maxT) / (1 - targetRatioBelow);
    }
    // Se la velocità ha meno negativo (raro), estendi il suo minimo
    if (ratioBelowV < targetRatioBelow) {
        alignMinV = - (targetRatioBelow * maxV) / (1 - targetRatioBelow);
    }

    const alignDeltaT = alignMaxT - alignMinT || 1;
    const alignDeltaV = alignMaxV - alignMinV || 1;

    // Tempo comune
    const timeMax = Math.max(...tData.map(d => d.t), ...vData.map(d => d.t));
    const timeMin = Math.min(...tData.map(d => d.t), ...vData.map(d => d.t));
    const timeDelta = timeMax - timeMin || 1;

    // --- DISEGNO ---

    // 6. Disegna Griglia (Usando i valori allineati della Traiettoria come base)
    // Nota: Lo zero della griglia ora corrisponderà perfettamente allo zero della velocità
    drawGrid(ctx, { 
        padding, width, height, chartWidth, chartHeight, 
        minT: timeMin, deltaT: timeDelta, 
        minY: alignMinT, deltaY: alignDeltaT, 
        style: TRAJECTORY_STYLE, 
        xFormatter: v => v.toFixed(2), 
        yFormatter: v => v.toFixed(0) // Mostra spostamento in cm
    });

    // Linea Zero Comune (Disegnata una sola volta, valida per entrambi)
    const zeroY = height - padding - ((0 - alignMinT) / alignDeltaT) * chartHeight;
    if (zeroY >= padding && zeroY <= height - padding) {
        ctx.strokeStyle = '#64748b'; // Grigio neutro
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(padding, zeroY); ctx.lineTo(width - padding, zeroY); ctx.stroke();
        ctx.setLineDash([]);
    }

    if (phaseTimes) drawPhasesBackground(ctx, phaseTimes, timeMin, timeDelta, padding, chartWidth, chartHeight);

    // 7. Traiettoria (Verde) - Usando dati spostati e range allineato
    ctx.lineWidth = 3;
    ctx.strokeStyle = TRAJECTORY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.shadowColor = TRAJECTORY_STYLE.lineShadow;
    ctx.shadowBlur = 10;
    ctx.beginPath();
    shiftedTData.forEach((point, i) => {
        const x = padding + ((point.t - timeMin) / timeDelta) * chartWidth;
        const y = height - padding - ((point.y - alignMinT) / alignDeltaT) * chartHeight;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    // 8. Velocità (Viola) - Usando range allineato
    ctx.lineWidth = 3;
    ctx.strokeStyle = VELOCITY_STYLE.line;
    ctx.shadowColor = VELOCITY_STYLE.lineShadow;
    ctx.shadowBlur = 10;
    ctx.beginPath();
    vData.forEach((point, i) => {
        const x = padding + ((point.t - timeMin) / timeDelta) * chartWidth;
        const y = height - padding - ((point.v - alignMinV) / alignDeltaV) * chartHeight;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;
    
    // 9. Label Asse Destro (Velocità)
    ctx.fillStyle = VELOCITY_STYLE.label;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= GRID_STEPS; i++) {
      const ratio = i / GRID_STEPS;
      const y = padding + (chartHeight * ratio);
      // Calcola il valore corrispondente sulla scala velocità allineata
      const val = alignMinV + (alignDeltaV * (GRID_STEPS - i) / GRID_STEPS);
      ctx.fillText(val.toFixed(0), width - padding + 8, y);
    }
    
    if (phaseTimes) drawPhaseMarkers(ctx, phaseTimes, timeMin, timeDelta, padding, chartWidth, height);
  }

  function drawGrid(ctx, { padding, width, height, chartWidth, chartHeight, minT, deltaT, minY, deltaY, style, xFormatter, yFormatter }) {
    ctx.strokeStyle = style.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = style.label;
    ctx.font = '10px Inter';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    for (let i = 0; i <= GRID_STEPS; i++) {
      const ratio = i / GRID_STEPS;
      const y = padding + (chartHeight * ratio);
      const val = minY + (deltaY * (GRID_STEPS - i) / GRID_STEPS);
      
      ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
      ctx.fillText(yFormatter(val), padding - 8, y);
    }

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const stepsX = 5;
    for (let i = 0; i <= stepsX; i++) {
        const ratio = i / stepsX;
        const x = padding + (chartWidth * ratio);
        const val = minT + (deltaT * ratio);
        ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
        ctx.fillText(xFormatter(val), x, height - padding + 8);
    }
  }

  function drawPhasesBackground(ctx, phases, minT, deltaT, padding, chartWidth, chartHeight) {
    const drawRect = (start, end, color) => {
        if (start != null && end != null) {
            const x1 = padding + ((start - minT) / deltaT) * chartWidth;
            const x2 = padding + ((end - minT) / deltaT) * chartWidth;
            ctx.fillStyle = color;
            ctx.fillRect(x1, padding, x2 - x1, chartHeight);
        }
    };
    drawRect(phases.eccentricStart, phases.eccentricEnd, 'rgba(255, 165, 0, 0.1)');
    drawRect(phases.concentricStart, phases.concentricEnd, 'rgba(74, 222, 128, 0.1)');
  }

  function drawPhaseMarkers(ctx, phases, minT, deltaT, padding, chartWidth, height) {
      const drawLine = (t, color) => {
          if(t == null) return;
          const x = padding + ((t - minT) / deltaT) * chartWidth;
          ctx.strokeStyle = color;
          ctx.setLineDash([4, 4]);
          ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
          ctx.setLineDash([]);
      };
      drawLine(phases.contactStart, 'rgba(255, 255, 0, 0.6)');
      drawLine(phases.eccentricEnd, 'rgba(255, 165, 0, 0.6)');
      drawLine(phases.takeoff, 'rgba(255, 0, 0, 0.6)');
  }

  function handleConcludeSession() {
    view = 'summary';
    // Reset l'hash quando si va in summary per evitare problemi quando si torna
    lastAddedJumpHash = null;
  }
  
  function handleBackToAnalysis() {
    view = 'analysis';
    // Non resettare l'hash - lascia che il controllo di esistenza gestisca i duplicati
    // Se results è già nella sessione, lastAddedJumpHash verrà aggiornato dalla reattività
  }
  
  function handleExitNoSave() {
    dispatch('exitNoSave');
  }
  
  function handleUploadComplete() {
    dispatch('uploadComplete');
  }
  
  $: currentJump = $sessionStore.jumps[$sessionStore.currentJumpIndex] || results || {};
</script>

{#if view === 'summary'}
  <div class="fixed inset-x-0 top-14 bottom-0 z-50 bg-slate-950 overflow-auto">
    <SummaryView 
      on:backToAnalysis={handleBackToAnalysis}
      on:exitNoSave={handleExitNoSave}
      on:uploadComplete={handleUploadComplete}
    />
  </div>
{:else}
<div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden relative ring-1 ring-white/5 flex flex-col h-full w-full">
  
  <!-- 1. STICKY HEADER -->
  <div class="shrink-0 bg-slate-900 z-10">
    <div class="px-5 py-3 flex items-center justify-between bg-emerald-950/30 border-b border-emerald-500/10">
         <div class="flex items-center gap-2.5">
            <span class="relative flex h-2.5 w-2.5">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            <span class="text-emerald-400 text-xs font-bold uppercase tracking-wider">
              {currentJump?.jump_detected ? 'Analisi Completata' : 'Salto Non Valido'}
            </span>
         </div>
         <span class="text-[10px] text-slate-500 font-mono bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
           SESSIONE IN CORSO • {$sessionStore.jumps.length} SALTI
         </span>
    </div>
    
    <div class="flex border-b border-slate-800 bg-slate-900/50">
       <button 
         on:click={() => activeTab = 'metrics'}
         class={`flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-all relative ${activeTab === 'metrics' ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}
       >
         <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class={activeTab==='metrics'?'text-indigo-400':''}><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
         Metriche
         {#if activeTab === 'metrics'}
            <div class="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]"></div>
         {/if}
       </button>

       <button 
         on:click={() => activeTab = 'charts'}
         class={`flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-all relative ${activeTab === 'charts' ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}
       >
         <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class={activeTab==='charts'?'text-indigo-400':''}><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
         Grafici
         {#if activeTab === 'charts'}
            <div class="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]"></div>
         {/if}
       </button>
    </div>
  </div>

  <!-- 2. SCROLLABLE CONTENT -->
  <div class="flex-1 overflow-y-auto p-5 custom-scrollbar bg-slate-900/50">
    
    {#if activeTab === 'metrics'}
      <div class="space-y-5">
         <div class="grid grid-cols-2 gap-3">
            <!-- Altezza Max -->
            <div class="relative group flex flex-col p-3 bg-slate-900/40 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-all hover:bg-slate-800/60">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] text-slate-400 uppercase tracking-wide font-semibold">Altezza Max</span>
                    <svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                </div>
                <div class="flex items-baseline gap-1 mt-auto">
                    <span class="text-2xl font-bold tracking-tight text-emerald-400">
                      {currentJump?.jump_detected ? (currentJump.max_height || '--') : '--'}
                    </span>
                    <span class="text-xs text-slate-500 font-medium">cm</span>
                </div>
            </div>
            
            <!-- Tempo Volo -->
            <div class="relative group flex flex-col p-3 bg-slate-900/40 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-all hover:bg-slate-800/60">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] text-slate-400 uppercase tracking-wide font-semibold">Tempo Volo</span>
                    <svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <div class="flex items-baseline gap-1 mt-auto">
                    <span class="text-2xl font-bold tracking-tight text-blue-400">
                      {currentJump?.jump_detected ? (currentJump.flight_time || '--') : '--'}
                    </span>
                    <span class="text-xs text-slate-500 font-medium">s</span>
                </div>
            </div>

            <!-- Vel Decollo -->
            <div class="relative group flex flex-col p-3 bg-slate-900/40 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-all hover:bg-slate-800/60">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] text-slate-400 uppercase tracking-wide font-semibold">Vel. Decollo</span>
                    <svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                </div>
                <div class="flex items-baseline gap-1 mt-auto">
                    <span class="text-2xl font-bold tracking-tight text-purple-400">
                      {currentJump?.jump_detected ? ((currentJump.calculated_takeoff_velocity || currentJump.takeoff_velocity || 0).toFixed(1)) : '--'}
                    </span>
                    <span class="text-xs text-slate-500 font-medium">cm/s</span>
                </div>
            </div>

            <!-- Potenza -->
            <div class="relative group flex flex-col p-3 bg-slate-900/40 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-all hover:bg-slate-800/60">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] text-slate-400 uppercase tracking-wide font-semibold">Potenza</span>
                    <svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                </div>
                <div class="flex items-baseline gap-1 mt-auto">
                    <span class="text-2xl font-bold tracking-tight text-amber-400">
                      {currentJump?.jump_detected ? ((currentJump.calculated_estimated_power || currentJump.estimated_power || 0).toFixed(0)) : '--'}
                    </span>
                    <span class="text-xs text-slate-500 font-medium">W</span>
                </div>
            </div>
         </div>

         <!-- Cards Dettagli -->
         <div class="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden shadow-sm">
            <div class="px-4 py-2 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                <h3 class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">Fasi Temporali</h3>
            </div>
            <div class="p-4 flex flex-col gap-0.5">
                <div class="flex justify-between items-center py-2 border-b border-slate-700/40 last:border-0">
                    <span class="text-sm text-slate-400 font-medium">Tempo Contatto</span>
                    <span class="text-sm font-mono font-bold text-slate-200">
                      {currentJump?.jump_detected ? ((currentJump.calculated_contact_time || currentJump.contact_time || 0).toFixed(3)) : '--'} s
                    </span>
                </div>
                <div class="flex justify-between items-center py-2 border-b border-slate-700/40 last:border-0">
                    <span class="text-sm text-slate-400 font-medium">Fase Eccentrica</span>
                    <span class="text-sm font-mono font-bold text-slate-200">
                      {currentJump?.jump_detected ? ((currentJump.calculated_eccentric_time || currentJump.eccentric_time || 0).toFixed(3)) : '--'} s
                    </span>
                </div>
                <div class="flex justify-between items-center py-2 border-b border-slate-700/40 last:border-0">
                    <span class="text-sm text-slate-400 font-medium">Fase Concentrica</span>
                    <span class="text-sm font-mono font-bold text-slate-200">
                      {currentJump?.jump_detected ? ((currentJump.calculated_concentric_time || currentJump.concentric_time || 0).toFixed(3)) : '--'} s
                    </span>
                </div>
            </div>
         </div>

         <div class="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden shadow-sm">
            <div class="px-4 py-2 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                <h3 class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">Biomeccanica</h3>
            </div>
            <div class="p-4 flex flex-col gap-0.5">
                <div class="flex justify-between items-center py-2 border-b border-slate-700/40 last:border-0">
                    <span class="text-sm text-slate-400 font-medium">Forza Media</span>
                    <span class="text-sm font-mono font-bold text-slate-200">
                      {currentJump?.jump_detected ? ((currentJump.calculated_average_force || currentJump.average_force || 0).toFixed(1)) : '--'} N
                    </span>
                </div>
                <div class="flex justify-between items-center py-2 border-b border-slate-700/40 last:border-0">
                    <span class="text-sm text-slate-400 font-medium">Salto Valido</span>
                    <span class={`text-sm font-mono font-bold px-2 py-0.5 rounded ${currentJump?.jump_detected ? 'text-emerald-400 bg-emerald-400/10' : 'text-red-400 bg-red-400/10'}`}>
                        {currentJump?.jump_detected ? 'Sì' : 'No'}
                    </span>
                </div>
            </div>
         </div>
      </div>
    {/if}

    {#if activeTab === 'charts'}
      <div class="h-full flex flex-col">
         <div class="flex justify-between items-center mb-4">
            <h3 class="text-xs font-bold text-slate-400 uppercase">Analisi Curve</h3>
            <div class="flex gap-1 bg-slate-800 p-1 rounded-lg border border-slate-700">
               <button on:click={() => activeGraph = 'trajectory'} class={`px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wide transition-all ${activeGraph === 'trajectory' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}>Pos.</button>
               <button on:click={() => activeGraph = 'velocity'} class={`px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wide transition-all ${activeGraph === 'velocity' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}>Vel.</button>
               <button on:click={() => activeGraph = 'combined'} class={`px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wide transition-all ${activeGraph === 'combined' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}>Conf.</button>
            </div>
         </div>

         <div class="flex-1 min-h-[250px] bg-slate-950 rounded-xl border border-slate-800 shadow-inner relative overflow-hidden group mb-4">
            <canvas bind:this={canvasRef} class="w-full h-full object-contain block"></canvas>
            
            <div class="absolute top-4 right-4 bg-slate-900/90 p-3 rounded-lg border border-slate-800 backdrop-blur-md shadow-xl pointer-events-none">
               {#if activeGraph === 'trajectory' || activeGraph === 'combined'}
               <div class="flex items-center gap-2 mb-2">
                   <div class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"></div>
                   <span class="text-[10px] font-medium text-slate-300">Altezza</span>
               </div>
               {/if}
               {#if activeGraph === 'velocity' || activeGraph === 'combined'}
               <div class="flex items-center gap-2">
                   <div class="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_8px_rgba(167,139,250,0.6)]"></div>
                   <span class="text-[10px] font-medium text-slate-300">Velocità</span>
               </div>
               {/if}
            </div>
         </div>
      </div>
    {/if}
  </div>

  <!-- 3. STICKY FOOTER -->
  <div class="shrink-0 p-4 bg-slate-900 border-t border-slate-800 z-20 shadow-[0_-5px_20px_rgba(0,0,0,0.3)]">
     {#if saveMessage}
        <div class="mb-3 text-center text-xs font-medium text-emerald-400 bg-emerald-900/20 py-1 rounded">{saveMessage}</div>
     {/if}
     <div class="grid grid-cols-2 gap-3">
        <button 
            on:click={handleConcludeSession}
            class="flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 py-3 rounded-xl text-sm font-semibold transition-all border border-slate-700 hover:border-slate-600 active:scale-[0.98]"
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
            Concludi Sessione
        </button>
        <button 
            on:click={() => dispatch('reset')}
            class="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/20 hover:shadow-indigo-900/40 active:scale-[0.98]"
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
            Nuova Analisi
        </button>
     </div>
  </div>
</div>
{/if}

<style>
  .custom-scrollbar::-webkit-scrollbar {
      width: 6px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
      background: rgba(15, 23, 42, 0.5);
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
      background: rgba(51, 65, 85, 0.8);
      border-radius: 3px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: rgba(71, 85, 105, 1);
  }
</style>