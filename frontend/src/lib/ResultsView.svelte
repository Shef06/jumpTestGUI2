<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { appState } from './stores.js';
  import { getBackendUrl } from './api.js';
  
  export let results;
  
  const dispatch = createEventDispatcher();
  
  let trajectoryCanvas;
  let velocityCanvas;
  let derivedVelocityData = [];
  
  const GRID_STEPS = 5;
  const TRAJECTORY_STYLE = {
    background: '#0f172a',
    grid: '#233044',
    axis: '#3c4b63',
    line: '#38bdf8',
    lineShadow: 'rgba(56, 189, 248, 0.35)',
    fill: 'rgba(56, 189, 248, 0.18)',
    label: '#94a3b8',
    zero: '#64748b'
  };
  const VELOCITY_STYLE = {
    background: '#121e33',
    grid: '#24324a',
    axis: '#3f4d66',
    line: '#c084fc',
    lineShadow: 'rgba(192, 132, 252, 0.35)',
    fillAbove: 'rgba(192, 132, 252, 0.18)',
    fillBelow: 'rgba(148, 163, 184, 0.12)',
    label: '#a5b4fc',
    zero: '#64748b'
  };
  
  onMount(() => {
    if (trajectoryCanvas && $appState.trajectoryData.length > 0) {
      drawTrajectoryChart();
    }
    if (velocityCanvas && derivedVelocityData.length > 0) {
      drawVelocityChart();
    }
  });

  $: derivedVelocityData = computeDerivedVelocity($appState.trajectoryData);
  
  $: if (trajectoryCanvas) {
    if ($appState.trajectoryData.length > 0) {
      drawTrajectoryChart();
    } else {
      clearCanvas(trajectoryCanvas, TRAJECTORY_STYLE.background);
    }
  }
  
  $: if (velocityCanvas) {
    if (derivedVelocityData.length > 0) {
      drawVelocityChart();
    } else {
      clearCanvas(velocityCanvas, VELOCITY_STYLE.background);
    }
  }

  function computeDerivedVelocity(data = []) {
    if (!data || data.length < 2) {
      return [];
    }

    const velocities = [];
    for (let i = 1; i < data.length; i++) {
      const prev = data[i - 1];
      const curr = data[i];
      const deltaT = curr.t - prev.t;
      if (!isFinite(deltaT) || deltaT === 0) {
        continue;
      }
      const deltaY = curr.y - prev.y;
      velocities.push({
        t: curr.t,
        v: deltaY / deltaT
      });
    }

    if (velocities.length === 0) {
      return [];
    }

    // Aggiungi un punto iniziale a 0 per rendere più chiaro il grafico
    return [{ t: velocities[0].t, v: 0 }, ...velocities];
  }
  
  function drawTrajectoryChart() {
    const ctx = trajectoryCanvas.getContext('2d');
    const width = trajectoryCanvas.width;
    const height = trajectoryCanvas.height;
    const padding = 52;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    clearCanvas(trajectoryCanvas, TRAJECTORY_STYLE.background);
    
    const data = $appState.trajectoryData;
    if (data.length === 0) return;
    
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxY = Math.max(...data.map(d => d.y));
    const minY = Math.min(...data.map(d => d.y));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaY = maxY === minY ? 1 : (maxY - minY);
    
    drawGrid(ctx, {
      padding,
      width,
      height,
      chartWidth,
      chartHeight,
      minT,
      deltaT,
      minY,
      deltaY,
      style: TRAJECTORY_STYLE,
      xFormatter: (value) => value.toFixed(2),
      yFormatter: (value) => value.toFixed(1)
    });
    
    if (minY <= 0 && maxY >= 0) {
      const zeroY = height - padding - ((0 - minY) / deltaY) * chartHeight;
      ctx.strokeStyle = TRAJECTORY_STYLE.zero;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(padding, zeroY);
      ctx.lineTo(width - padding, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    
    ctx.lineWidth = 3;
    ctx.strokeStyle = TRAJECTORY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = TRAJECTORY_STYLE.lineShadow;
    ctx.shadowBlur = 12;
    
    ctx.beginPath();
    data.forEach((point, i) => {
      const x = padding + ((point.t - minT) / deltaT) * chartWidth;
      const y = height - padding - ((point.y - minY) / deltaY) * chartHeight;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    
    ctx.shadowBlur = 0;
    ctx.lineTo(padding + chartWidth, height - padding);
    ctx.lineTo(padding, height - padding);
    ctx.closePath();
    ctx.fillStyle = TRAJECTORY_STYLE.fill;
    ctx.fill();
    
    ctx.fillStyle = TRAJECTORY_STYLE.line;
    data.forEach((point, i) => {
      if (i % Math.max(1, Math.floor(data.length / 25)) === 0 || i === data.length - 1) {
        const x = padding + ((point.t - minT) / deltaT) * chartWidth;
        const y = height - padding - ((point.y - minY) / deltaY) * chartHeight;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    
    drawLabels(ctx, {
      width,
      height,
      padding,
      xText: 'Tempo (s)',
      yText: 'Altezza (cm)',
      style: TRAJECTORY_STYLE
    });
  }
  
  function drawVelocityChart() {
    const ctx = velocityCanvas.getContext('2d');
    const width = velocityCanvas.width;
    const height = velocityCanvas.height;
    const padding = 52;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    clearCanvas(velocityCanvas, VELOCITY_STYLE.background);
    
    const data = derivedVelocityData;
    if (data.length === 0) return;
    
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxV = Math.max(...data.map(d => d.v));
    const minV = Math.min(...data.map(d => d.v));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaV = maxV === minV ? (Math.abs(maxV) || 1) : (maxV - minV);
    
    drawGrid(ctx, {
      padding,
      width,
      height,
      chartWidth,
      chartHeight,
      minT,
      deltaT,
      minY: minV,
      deltaY: deltaV,
      style: VELOCITY_STYLE,
      xFormatter: (value) => value.toFixed(2),
      yFormatter: (value) => value.toFixed(1),
      invertYLabel: false,
      rightSideLabels: true
    });
    
    if (minV <= 0 && maxV >= 0) {
      const zeroY = height - padding - ((0 - minV) / deltaV) * chartHeight;
      ctx.strokeStyle = VELOCITY_STYLE.zero;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(padding, zeroY);
      ctx.lineTo(width - padding, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    
    ctx.lineWidth = 3;
    ctx.strokeStyle = VELOCITY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = VELOCITY_STYLE.lineShadow;
    ctx.shadowBlur = 12;
    
    const pathPoints = [];
    ctx.beginPath();
    data.forEach((point, i) => {
      const x = padding + ((point.t - minT) / deltaT) * chartWidth;
      const y = height - padding - ((point.v - minV) / deltaV) * chartHeight;
      pathPoints.push({ x, y });
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    ctx.shadowBlur = 0;
    
    fillVelocityAreas(ctx, pathPoints, {
      padding,
      height,
      minV,
      deltaV,
      chartHeight,
      style: VELOCITY_STYLE
    });
    
    ctx.fillStyle = VELOCITY_STYLE.line;
    pathPoints.forEach((point, i) => {
      if (i % Math.max(1, Math.floor(pathPoints.length / 25)) === 0 || i === pathPoints.length - 1) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    
    drawLabels(ctx, {
      width,
      height,
      padding,
      xText: 'Tempo (s)',
      yText: 'Velocità (cm/s)',
      style: VELOCITY_STYLE
    });
  }

  function clearCanvas(canvas, background) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawGrid(ctx, {
    padding,
    width,
    height,
    chartWidth,
    chartHeight,
    minT,
    deltaT,
    minY,
    deltaY,
    style,
    xFormatter,
    yFormatter,
    invertYLabel = true,
    rightSideLabels = false
  }) {
    ctx.strokeStyle = style.axis;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    ctx.strokeStyle = style.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = style.label;
    ctx.font = '11px sans-serif';
    ctx.textBaseline = 'middle';

    for (let i = 0; i <= GRID_STEPS; i++) {
      const ratio = i / GRID_STEPS;
      const y = padding + (chartHeight * ratio);
      const value = invertYLabel
        ? (minY + (deltaY * (GRID_STEPS - i) / GRID_STEPS))
        : (minY + (deltaY * i / GRID_STEPS));

      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();

      const label = yFormatter(value);
      const labelX = rightSideLabels ? width - padding + 12 : padding - 12;
      const align = rightSideLabels ? 'left' : 'right';
      ctx.textAlign = align;
      ctx.fillText(label, labelX, y);
    }

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let i = 0; i <= GRID_STEPS; i++) {
      const ratio = i / GRID_STEPS;
      const x = padding + (chartWidth * ratio);
      const value = minT + (deltaT * ratio);

      ctx.beginPath();
      ctx.moveTo(x, padding);
      ctx.lineTo(x, height - padding);
      ctx.stroke();

      const label = xFormatter(value);
      ctx.fillText(label, x, height - padding + 12);
    }
  }

  function drawLabels(ctx, { width, height, padding, xText, yText, style }) {
    ctx.fillStyle = style.label;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText(xText, width / 2, height - 18);
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText(yText, 0, 0);
    ctx.restore();
  }

  function fillVelocityAreas(ctx, points, { padding, height, minV, deltaV, chartHeight, style }) {
    if (points.length < 2) return;

    const leftX = points[0].x;
    const rightX = points[points.length - 1].x;
    const zeroRatio = (0 - minV) / deltaV;
    const zeroY = height - padding - zeroRatio * chartHeight;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(leftX, height - padding);
    points.forEach(point => ctx.lineTo(point.x, point.y));
    ctx.lineTo(rightX, height - padding);
    ctx.closePath();
    ctx.clip();

    if (zeroRatio <= 0) {
      ctx.fillStyle = style.fillAbove;
      ctx.fillRect(leftX, padding, rightX - leftX, height - padding);
    } else if (zeroRatio >= 1) {
      ctx.fillStyle = style.fillBelow;
      ctx.fillRect(leftX, padding, rightX - leftX, height - padding);
    } else {
      ctx.fillStyle = style.fillAbove;
      ctx.fillRect(leftX, padding, rightX - leftX, zeroY - padding);
      ctx.fillStyle = style.fillBelow;
      ctx.fillRect(leftX, zeroY, rightX - leftX, height - padding - (zeroY - padding));
    }
    ctx.restore();
  }
  
  function handleReset() {
    dispatch('reset');
  }

  let isSaving = false;
  let saveMessage = '';

  async function saveResults() {
    isSaving = true;
    saveMessage = '';
    
    try {
      const response = await fetch(`${getBackendUrl()}/api/results/save`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        saveMessage = 'Risultati salvati con successo!';
      } else {
        saveMessage = data.error || 'Errore durante il salvataggio';
      }
    } catch (error) {
      saveMessage = 'Errore di connessione al server';
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="results-container bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700 h-full flex flex-col">
  <div class="results-header bg-gradient-to-r from-green-600 to-teal-600 px-6 py-4">
    <h2 class="text-xl font-semibold text-white">Risultati Analisi</h2>
    <p class="text-green-100 text-sm mt-1">Analisi completata con successo</p>
  </div>
  
  <div class="results-content p-6 space-y-6 flex-1 overflow-auto">
    <!-- Main Metrics -->
    <div class="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Metriche Principali</h3>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-xs text-slate-400 mb-1">Altezza Max</p>
          <p class="text-2xl font-bold text-green-400">{results.max_height} cm</p>
        </div>
        <div>
          <p class="text-xs text-slate-400 mb-1">Tempo di Volo</p>
          <p class="text-2xl font-bold text-blue-400">{results.flight_time} s</p>
        </div>
        <div>
          <p class="text-xs text-slate-400 mb-1">Velocità Decollo</p>
          <p class="text-2xl font-bold text-purple-400">{results.takeoff_velocity} cm/s</p>
        </div>
        <div>
          <p class="text-xs text-slate-400 mb-1">Potenza Est.</p>
          <p class="text-2xl font-bold text-yellow-400">{results.estimated_power} W</p>
        </div>
      </div>
    </div>
    
    <!-- Phase Timing -->
    <div class="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Analisi Fasi</h3>
      <div class="space-y-3">
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Tempo Contatto</span>
          <span class="text-lg font-semibold text-white">{results.contact_time} s</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Fase Eccentrica</span>
          <span class="text-lg font-semibold text-white">{results.eccentric_time} s</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Fase Concentrica</span>
          <span class="text-lg font-semibold text-white">{results.concentric_time} s</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Tempo Caduta</span>
          <span class="text-lg font-semibold text-white">{results.fall_time} s</span>
        </div>
      </div>
    </div>
    
    <!-- Biomechanical Parameters -->
    <div class="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Parametri Biomeccanici</h3>
      <div class="space-y-3">
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Forza Media</span>
          <span class="text-lg font-semibold text-white">{results.average_force} N</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-sm text-slate-400">Salto Rilevato</span>
          <span class="text-lg font-semibold {results.jump_detected ? 'text-green-400' : 'text-red-400'}">
            {results.jump_detected ? 'Sì' : 'No'}
          </span>
        </div>
      </div>
    </div>
    
    <!-- Trajectory Chart -->
    {#if $appState.trajectoryData.length > 0}
      <div class="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Traiettoria del Salto</h3>
        <canvas
          bind:this={trajectoryCanvas}
          width="400"
          height="250"
          class="w-full rounded-lg"
        ></canvas>
      </div>
    {/if}
    
    <!-- Velocity Chart -->
    {#if derivedVelocityData.length > 0}
      <div class="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Velocità nel Tempo</h3>
        <canvas
          bind:this={velocityCanvas}
          width="400"
          height="250"
          class="w-full rounded-lg"
        ></canvas>
      </div>
    {/if}
    
    <!-- Save message -->
    {#if saveMessage}
      <div class="bg-blue-500/10 border border-blue-500/50 rounded-lg p-4">
        <p class="text-blue-400 text-sm">{saveMessage}</p>
      </div>
    {/if}
    
    <!-- Actions -->
    <div class="flex gap-3 pt-4">
      <button
        on:click={saveResults}
        disabled={isSaving}
        class="flex-1 bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold hover:from-green-700 hover:to-teal-700 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        {isSaving ? 'Salvataggio...' : 'Salva Risultati'}
      </button>
      <button
        on:click={handleReset}
        class="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl"
      >
        <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Nuova Analisi
      </button>
    </div>
  </div>
</div>

<style>
  .results-content::-webkit-scrollbar {
    width: 8px;
  }
  
  .results-content::-webkit-scrollbar-track {
    background: #1e293b;
    border-radius: 4px;
  }
  
  .results-content::-webkit-scrollbar-thumb {
    background: #475569;
    border-radius: 4px;
  }
  
  .results-content::-webkit-scrollbar-thumb:hover {
    background: #64748b;
  }
</style>