<script>
  import { createEventDispatcher } from 'svelte';
  import { sessionStore } from './stores.js';
  import { getBackendUrl, api } from './api.js';
  
  const dispatch = createEventDispatcher();
  
  let isUploading = false;
  let uploadMessage = '';
  let hasError = false;
  
  $: sessionJumps = $sessionStore.jumps;
  $: selectedJumpIds = $sessionStore.selectedJumpIds;
  
  // Resetta l'errore quando vengono selezionati dei salti
  $: if (selectedJumpIds.length > 0 && hasError) {
    hasError = false;
    uploadMessage = '';
  }
  
  // Calcola il best performer
  $: bestJumpId = sessionJumps.length > 0 
    ? sessionJumps.reduce((maxId, jump) => {
        if (!maxId) return jump.jump_detected ? jump.id : null;
        const currentMax = sessionJumps.find(j => j.id === maxId);
        return (jump.jump_detected && jump.max_height > (currentMax?.max_height || 0)) ? jump.id : maxId;
      }, null)
    : null;
  
  // Calcola statistiche
  $: validJumps = sessionJumps.filter(j => j.jump_detected);
  $: bestHeight = validJumps.length > 0 ? Math.max(...validJumps.map(j => j.max_height)) : 0;
  $: avgPower = validJumps.length > 0 
    ? Math.round(validJumps.reduce((acc, curr) => acc + (curr.calculated_estimated_power || curr.estimated_power || 0), 0) / validJumps.length)
    : 0;
  
  async function handleToggleSelect(jumpId) {
    let isSelected = false;
    sessionStore.update(state => {
      if (state.selectedJumpIds.includes(jumpId)) {
        isSelected = false;
        return {
          ...state,
          selectedJumpIds: state.selectedJumpIds.filter(id => id !== jumpId)
        };
      } else {
        isSelected = true;
        return {
          ...state,
          selectedJumpIds: [...state.selectedJumpIds, jumpId]
        };
      }
    });
    
    // Salva automaticamente quando viene selezionato/deselezionato un salto
    await saveJump(jumpId, isSelected);
  }
  
  async function saveJump(jumpId, isSelected = true) {
    let testId = typeof window !== 'undefined' ? sessionStorage.getItem('testId') : null;
    
    // Genera un testId se non esiste
    if (!testId && typeof window !== 'undefined') {
      testId = `test_${Date.now()}`;
      sessionStorage.setItem('testId', testId);
      console.log('testId generato automaticamente:', testId);
    }
    
    if (!testId) {
      console.warn('testId non disponibile, salvataggio saltato per jumpId:', jumpId);
      return;
    }
    
    const jump = sessionJumps.find(j => j.id === jumpId);
    if (!jump || !jump.jump_detected) {
      console.warn('Salto non trovato o non valido:', jumpId, jump);
      return;
    }
    
    try {
      const action = isSelected ? 'add' : 'remove';
      console.log(`Salvataggio salto ${action}:`, testId, jumpId, jump);
      const result = await api.saveResults(testId, {
        results: jump,
        trajectory: jump.trajectory || [],
        velocity: jump.velocity || [],
        settings: {
          mass: jump.body_mass_kg || 75,
          fps: jump.fps || 30
        }
      }, jumpId, action);
      console.log('Salvataggio completato:', result);
    } catch (error) {
      console.error('Errore nel salvataggio automatico:', error);
    }
  }
  
  async function handleSelectAll() {
    let newSelectedIds = [];
    let isSelecting = false;
    sessionStore.update(state => {
      if (state.selectedJumpIds.length === validJumps.length) {
        newSelectedIds = [];
        isSelecting = false;
        return { ...state, selectedJumpIds: [] };
      } else {
        newSelectedIds = validJumps.map(j => j.id);
        isSelecting = true;
        return { ...state, selectedJumpIds: newSelectedIds };
      }
    });
    
    // Salva automaticamente tutti i salti selezionati/deselezionati
    for (const jumpId of newSelectedIds.length > 0 ? newSelectedIds : validJumps.map(j => j.id)) {
      await saveJump(jumpId, isSelecting);
    }
  }
  
  async function handleDeselectAll() {
    const previousSelectedIds = [...selectedJumpIds];
    sessionStore.update(state => ({ ...state, selectedJumpIds: [] }));
    
    // Salva automaticamente tutti i salti deselezionati
    for (const jumpId of previousSelectedIds) {
      await saveJump(jumpId, false);
    }
  }
  
  async function handleUploadNow() {
    if (selectedJumpIds.length === 0) {
      hasError = true;
      uploadMessage = 'Seleziona almeno un salto';
      setTimeout(() => {
        uploadMessage = '';
        hasError = false;
      }, 5000);
      return;
    }
    
    hasError = false;
    // Qui andrà la logica di upload
  }
  
  function handleBackToAnalysis() {
    dispatch('backToAnalysis');
  }
  
  
</script>

<div class="min-h-screen w-full flex flex-col bg-slate-900 p-4 md:p-8 animate-in fade-in zoom-in-95 duration-300">
  
  <!-- Header Riepilogo -->
  <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4">
    <div>
        <div class="flex items-center gap-2 mb-1">
            <button 
              on:click={handleBackToAnalysis} 
              class="text-slate-400 hover:text-white transition-colors flex items-center gap-1 text-sm"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                Torna all'analisi
            </button>
        </div>
        <h1 class="text-3xl font-bold text-white mb-2">Riepilogo Sessione</h1>
        <p class="text-slate-400">Hai completato {sessionJumps.length} salti. Seleziona quelli da salvare.</p>
    </div>
    
    <!-- Session Quick Stats -->
    <div class="flex gap-4">
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 min-w-[120px]">
            <span class="text-xs text-slate-400 uppercase tracking-wider block mb-1">Miglior Altezza</span>
            <span class="text-2xl font-bold text-emerald-400">
              {bestHeight.toFixed(2)} <span class="text-sm font-normal text-slate-500">cm</span>
            </span>
        </div>
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 min-w-[120px]">
            <span class="text-xs text-slate-400 uppercase tracking-wider block mb-1">Media Potenza</span>
            <span class="text-2xl font-bold text-yellow-400">
                {avgPower} <span class="text-sm font-normal text-slate-500"> W</span>
            </span>
        </div>
    </div>
  </div>

  <!-- Banner Errore -->
  {#if hasError && uploadMessage}
    <div class="mb-6 bg-red-900/30 border-2 border-red-500/50 rounded-xl p-4 flex items-center gap-3 animate-in">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-red-400 flex-shrink-0">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <div class="flex-1">
        <h3 class="text-red-400 font-bold text-lg mb-1">Attenzione</h3>
        <p class="text-red-300 text-sm">{uploadMessage}</p>
      </div>
    </div>
  {/if}

  <!-- Tabella Salti -->
  <div class="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden flex-1 shadow-2xl mb-20">
    <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
            <thead>
                <tr class="bg-slate-900/50 border-b border-slate-700">
                    <th class="p-4 w-12 text-center">
                        <input 
                            type="checkbox" 
                            class="w-4 h-4 rounded border-slate-600 bg-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-800"
                            on:change={handleSelectAll}
                            checked={selectedJumpIds.length > 0 && selectedJumpIds.length === validJumps.length}
                        />
                    </th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">#</th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Altezza (cm)</th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider hidden md:table-cell">Potenza (W)</th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider hidden sm:table-cell">T. Volo (s)</th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider hidden lg:table-cell">T. Contatto (s)</th>
                    <th class="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Note</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-700">
                {#if sessionJumps.length === 0}
                  <tr>
                    <td colspan="7" class="p-8 text-center text-slate-400">
                      Nessun salto nella sessione
                    </td>
                  </tr>
                {:else}
                {#each sessionJumps as jump, idx}
                    {@const isBest = jump.id === bestJumpId}
                    {@const isSelected = selectedJumpIds.includes(jump.id)}
                    
                    <tr 
                        class="transition-colors hover:bg-slate-700/50 cursor-pointer {isSelected ? 'bg-indigo-900/10' : ''} {isBest ? 'bg-emerald-900/10' : ''}"
                        on:click={() => jump.jump_detected && handleToggleSelect(jump.id)}
                    >
                        <td class="p-4 text-center" on:click|stopPropagation={() => {}}>
                            <input 
                                type="checkbox" 
                                checked={isSelected}
                                on:change={() => handleToggleSelect(jump.id)}
                                disabled={!jump.jump_detected}
                                class="w-4 h-4 rounded border-slate-600 bg-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-800 disabled:opacity-50"
                            />
                        </td>
                        <td class="p-4 font-mono text-slate-400 text-sm">
                            {String(idx + 1).padStart(2, '0')}
                        </td>
                        <td class="p-4">
                            <div class="flex items-center gap-2">
                                <span class="text-lg font-bold {jump.jump_detected ? 'text-white' : 'text-slate-600'}">
                                    {jump.jump_detected ? jump.max_height.toFixed(2) : '--'}
                                </span>
                                {#if isBest && jump.jump_detected}
                                    <span class="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase border border-emerald-500/30">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                          <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                                        </svg>
                                        Best
                                    </span>
                                {/if}
                            </div>
                        </td>
                        <td class="p-4 hidden md:table-cell">
                            <span class="font-mono {jump.jump_detected ? 'text-yellow-400' : 'text-slate-600'}">
                                {jump.jump_detected ? (jump.calculated_estimated_power || jump.estimated_power || 0).toFixed(0) : '--'}
                            </span>
                        </td>
                        <td class="p-4 hidden sm:table-cell">
                            <span class="font-mono {jump.jump_detected ? 'text-blue-400' : 'text-slate-600'}">
                                {jump.jump_detected ? jump.flight_time : '--'}
                            </span>
                        </td>
                        <td class="p-4 hidden lg:table-cell">
                            <span class="font-mono {jump.jump_detected ? 'text-slate-300' : 'text-slate-600'}">
                                {jump.jump_detected ? (jump.calculated_contact_time || jump.contact_time || 0).toFixed(3) : '--'}
                            </span>
                        </td>
                        <td class="p-4">
                            {#if !jump.jump_detected}
                                <span class="text-red-400 text-xs flex items-center gap-1">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                                    </svg>
                                    Errore Acquisizione
                                </span>
                            {:else}
                                <span class="text-slate-500 text-xs">--</span>
                            {/if}
                        </td>
                    </tr>
                {/each}
                {/if}
            </tbody>
        </table>
    </div>
  </div>

  <!-- Sticky Footer Bar -->
  <div class="fixed bottom-6 left-1/2 transform -translate-x-1/2 w-[95%] max-w-5xl bg-slate-800/90 backdrop-blur-md border border-slate-600 p-4 rounded-2xl shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4 z-50">
    
    <!-- Sinistra: Info selezione -->
    <div class="flex items-center gap-4 w-full md:w-auto justify-between md:justify-start">
        <span class="text-slate-300 font-medium">
            <span class="text-white font-bold">{selectedJumpIds.length}</span> salti selezionati
        </span>
        <button 
            class="text-slate-400 hover:text-red-400 text-sm flex items-center gap-1 transition-colors px-3 py-2 rounded-lg hover:bg-slate-700/50"
            on:click={handleDeselectAll}
            disabled={selectedJumpIds.length === 0}
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            <span class="hidden sm:inline">Deseleziona tutti</span>
        </button>
    </div>
    
    <!-- Destra: Azioni Principali -->
    <div class="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
        
        {#if uploadMessage}
          <div class="text-center text-sm font-semibold {uploadMessage.includes('completato') ? 'text-emerald-400' : 'text-red-400'} bg-slate-900/80 py-2 px-4 rounded-lg border {uploadMessage.includes('completato') ? 'border-emerald-500/30' : 'border-red-500/50'} flex items-center gap-2 animate-in">
            {#if !uploadMessage.includes('completato')}
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            {/if}
            {uploadMessage}
          </div>
        {/if}
        
        <!-- Pulsante Uscita senza salvare -->
        <button 
            id="exitWithutSavingBtn"
            class="w-full sm:w-auto text-red-400 hover:text-red-300 text-sm font-medium transition-colors px-4 py-2 flex items-center justify-center gap-2 hover:bg-red-500/10 rounded-xl"
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            Esci senza salvare
        </button>

        <!-- Pulsante Upload Dopo -->
        <button 
          id="uploadLaterBtn"
          class="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl font-medium transition-all border border-slate-600 hover:border-slate-500 shadow-sm"
          disabled={isUploading}
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <span>Upload dopo</span>
        </button>
        
        <!-- Pulsante Upload Adesso (Primario) -->
        <button 
          id="uploadBtn"
          class="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-bold transition-all shadow-lg transform active:scale-95 hover:-translate-y-0.5 {hasError ? 'bg-red-600 hover:bg-red-500 text-white border-2 border-red-400 shadow-red-900/50 animate-pulse' : selectedJumpIds.length === 0 ? 'bg-slate-600 text-slate-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-900/50'}"
          on:click={handleUploadNow}
          disabled={isUploading}
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <span>Upload adesso</span>
        </button>
    </div>
  </div>

</div>

<style>
  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  @keyframes zoom-in-95 {
    from { transform: scale(0.95); }
    to { transform: scale(1); }
  }
  
  .animate-in {
    animation: fade-in 0.3s ease-out, zoom-in-95 0.3s ease-out;
  }
</style>

