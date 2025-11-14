<script>
  import { createEventDispatcher } from 'svelte';

  export let show = false;
  export let loading = false;
  export let cameras = [];
  export let selectedIndex = null;
  export let error = '';

  const dispatch = createEventDispatcher();

  function onClose() {
    dispatch('close');
  }

  function onConfirm() {
    dispatch('confirm');
  }

  function onChange(e) {
    const idx = Number(e.target.value);
    dispatch('select', { index: idx });
  }
</script>

{#if show}
  <div 
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
    role="dialog"
    aria-modal="true"
    aria-labelledby="camera-modal-title"
    on:click|self={onClose}
    on:keydown={(e) => e.key === 'Escape' && onClose()}
  >
    <div class="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md shadow-2xl" role="document">
      <div class="px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-700 flex items-center justify-between">
        <h4 id="camera-modal-title" class="text-white font-semibold text-lg">Seleziona fotocamera</h4>
        <button 
          class="text-slate-400 hover:text-white focus:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-800 rounded p-1"
          on:click={onClose}
          aria-label="Chiudi modal"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="p-4 sm:p-6 space-y-4">
        {#if error}
          <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-3 text-red-300 text-sm" role="alert">
            {error}
          </div>
        {/if}
        {#if loading}
          <div class="flex items-center gap-3" role="status" aria-live="polite">
            <svg class="animate-spin h-5 w-5 text-purple-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="text-slate-300">Caricamento fotocamere...</p>
          </div>
        {:else}
          {#if cameras.length > 0}
            <div>
              <label for="camera-select" class="block text-sm font-medium text-slate-300 mb-2">Fotocamera</label>
              <select 
                id="camera-select" 
                class="input-field" 
                on:change={onChange} 
                bind:value={selectedIndex}
                aria-describedby="camera-select-help"
              >
                {#each cameras as cam, i}
                  <option value={i}>{cam.label || `Camera ${i + 1}`}</option>
                {/each}
              </select>
              <p id="camera-select-help" class="sr-only">Seleziona una fotocamera dalla lista</p>
            </div>
          {:else}
            <p class="text-slate-400" role="status">Nessuna fotocamera disponibile.</p>
          {/if}
        {/if}
      </div>
      <div class="px-4 sm:px-6 py-3 sm:py-4 border-t border-slate-700 flex gap-2 sm:gap-3 justify-end">
        <button 
          class="btn-secondary" 
          on:click={onClose}
          aria-label="Annulla selezione fotocamera"
        >
          Annulla
        </button>
        <button 
          class="btn-primary" 
          disabled={loading || cameras.length === 0} 
          on:click={onConfirm}
          aria-label="Conferma selezione e avvia anteprima"
        >
          Conferma e anteprima
        </button>
      </div>
    </div>
  </div>
{/if}



