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
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    <div class="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md shadow-2xl">
      <div class="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <h4 class="text-white font-semibold">Seleziona fotocamera</h4>
        <button class="text-slate-300 hover:text-white" on:click={onClose}>✕</button>
      </div>
      <div class="p-6 space-y-4">
        {#if error}
          <div class="bg-red-500/10 border border-red-500/50 rounded-lg p-3 text-red-300 text-sm">{error}</div>
        {/if}
        {#if loading}
          <p class="text-slate-300">Caricamento fotocamere...</p>
        {:else}
          {#if cameras.length > 0}
            <label for="camera-select" class="block text-sm font-medium text-slate-300 mb-2">Fotocamera</label>
            <select id="camera-select" class="input-field" on:change={onChange} bind:value={selectedIndex}>
              {#each cameras as cam, i}
                <option value={i}>{cam.label || `Camera ${i}`}</option>
              {/each}
            </select>
          {:else}
            <p class="text-slate-400">Nessuna fotocamera disponibile.</p>
          {/if}
        {/if}
      </div>
      <div class="px-6 py-4 border-t border-slate-700 flex gap-2 justify-end">
        <button class="btn-secondary" on:click={onClose}>Annulla</button>
        <button class="btn-primary" disabled={loading || cameras.length === 0} on:click={onConfirm}>
          Conferma e anteprima
        </button>
      </div>
    </div>
  </div>
{/if}

