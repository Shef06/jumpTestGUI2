<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { appState } from './stores.js';
  
  export let results;
  
  const dispatch = createEventDispatcher();
  
  let trajectoryCanvas;
  let velocityCanvas;
  
  onMount(() => {
    if (trajectoryCanvas && $appState.trajectoryData.length > 0) {
      drawTrajectoryChart();
    }
    if (velocityCanvas && $appState.velocityData.length > 0) {
      drawVelocityChart();
    }
  });
  
  function drawTrajectoryChart() {
    const ctx = trajectoryCanvas.getContext('2d');
    const width = trajectoryCanvas.width;
    const height = trajectoryCanvas.height;
    
    // Clear
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, width, height);
    
    const data = $appState.trajectoryData;
    if (data.length === 0) return;
    
    // Find bounds
    const maxT = Math.max(...data.map(d => d.t));
    const maxY = Math.max(...data.map(d => d.y));
    const minY = Math.min(...data.map(d => d.y));
    
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    // Draw axes
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();
    
    // Draw grid
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding + (chartHeight * i / 5);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }
    
    // Draw data
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    data.forEach((point, i) => {
      const x = padding + (point.t / maxT) * chartWidth;
      const y = height - padding - ((point.y - minY) / (maxY - minY)) * chartHeight;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px sans-serif';
    ctx.fillText('Tempo (s)', width / 2 - 30, height - 10);
    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Altezza (cm)', 0, 0);
    ctx.restore();
  }
  
  function drawVelocityChart() {
    const ctx = velocityCanvas.getContext('2d');
    const width = velocityCanvas.width;
    const height = velocityCanvas.height;
    
    // Clear
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, width, height);
    
    const data = $appState.velocityData;
    if (data.length === 0) return;
    
    // Find bounds
    const maxT = Math.max(...data.map(d => d.t));
    const maxV = Math.max(...data.map(d => Math.abs(d.v)));
    
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    // Draw axes
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();
    
    // Zero line
    const zeroY = height - padding - (chartHeight / 2);
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    ctx.lineTo(width - padding, zeroY);
    ctx.stroke();
    
    // Draw data
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    data.forEach((point, i) => {
      const x = padding + (point.t / maxT) * chartWidth;
      const y = zeroY - (point.v / maxV) * (chartHeight / 2);
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px sans-serif';
    ctx.fillText('Tempo (s)', width / 2 - 30, height - 10);
    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Velocità (cm/s)', 0, 0);
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
      const response = await fetch('http://localhost:5000/api/results/save', {
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
    {#if $appState.velocityData.length > 0}
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