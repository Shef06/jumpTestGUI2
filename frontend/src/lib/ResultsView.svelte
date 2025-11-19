<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { appState } from './stores.js';
  import { getBackendUrl } from './api.js';
  
  export let results;
  
  const dispatch = createEventDispatcher();
  
  const g = 9.81; // Accelerazione di gravità in m/s²
  
  let trajectoryCanvas;
  let velocityCanvas;
  let combinedCanvas;
  let fullscreenChart = null; // 'trajectory' | 'velocity' | 'combined' | null
  let fullscreenTrajectoryCanvas;
  let fullscreenVelocityCanvas;
  let fullscreenCombinedCanvas;
  let derivedVelocityData = []; // Ricevuto dal backend
  let phaseTimes = null; // Ricevuto dal backend
  
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
    
    // Listener globale per ESC
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });

  // Inizializza i dati dai results quando arrivano
  $: if (results) {
    derivedVelocityData = results.velocity || [];
    phaseTimes = results.phase_times || null;
    // Aggiorna anche trajectoryData nello store se disponibile
    if (results.trajectory) {
      $appState.trajectoryData = results.trajectory;
    }
  }
  
  // Tutte le funzioni di calcolo sono state spostate nel backend
  
  // Funzione helper per ottenere i tempi delle fasi (ora usa i dati dal backend)
  function getPhaseTimes() {
    return phaseTimes;
  }
  
  // Funzione per calcolare la forza media dalla velocità (RIMOSSA - ora calcolata nel backend)
  function calculateAverageForceFromVelocity(velocityData, trajectoryData, bodyMassKg = 70.0) {
    if (!velocityData || velocityData.length < 2 || bodyMassKg <= 0) {
      return 0;
    }
    
    // Identifica la fase di contatto: quando l'altezza è vicina a 0 o negativa
    const CONTACT_THRESHOLD = 5.0; // cm - soglia per considerare l'atleta a contatto con il suolo
    
    // Crea una mappa per l'altezza per accesso rapido
    const heightMap = new Map();
    if (trajectoryData && trajectoryData.length > 0) {
      trajectoryData.forEach(point => {
        heightMap.set(point.t, point.y);
      });
    }
    
    // Calcola l'accelerazione dalla velocità
    const accelerations = [];
    for (let i = 1; i < velocityData.length; i++) {
      const prev = velocityData[i - 1];
      const curr = velocityData[i];
      const deltaT = curr.t - prev.t;
      
      if (deltaT > 0 && isFinite(deltaT)) {
        // Velocità in m/s
        const v1_ms = prev.v / 100;
        const v2_ms = curr.v / 100;
        const a_ms2 = (v2_ms - v1_ms) / deltaT;
        
        accelerations.push({
          time: curr.t,
          a_ms2: a_ms2,
          velocity: curr.v
        });
      }
    }
    
    if (accelerations.length === 0) {
      return 0;
    }
    
    // Calcola la forza istantanea solo durante la fase di contatto
    const forces = [];
    
    for (let i = 0; i < accelerations.length; i++) {
      const acc = accelerations[i];
      const height = heightMap.get(acc.time);
      
      // Considera solo i punti durante il contatto (altezza <= CONTACT_THRESHOLD)
      // e durante la fase concentrica (velocità positiva o in aumento)
      const isInContact = height !== undefined && Math.abs(height) <= CONTACT_THRESHOLD;
      
      if (isInContact && Math.abs(acc.a_ms2) > 0.05) { // Soglia per filtrare il rumore
        // Forza: F = m * (a + g)
        // Durante il contatto, la forza totale è m * (a + g) dove a è l'accelerazione verso l'alto
        const force = bodyMassKg * (acc.a_ms2 + g);
        
        // Considera solo forze positive significative (verso l'alto, durante la fase concentrica)
        if (force > bodyMassKg * g * 0.3 && acc.velocity >= 0) {
          forces.push(force);
        }
      }
    }
    
    if (forces.length === 0) {
      return 0;
    }
    
    // Calcola la media delle forze durante il contatto
    const averageForce = forces.reduce((sum, f) => sum + f, 0) / forces.length;
    
    return averageForce;
  }
  
  // Funzione per calcolare la velocità di decollo
  function calculateTakeoffVelocity(trajectoryData, velocityData) {
    if (!trajectoryData || trajectoryData.length < 2 || !velocityData || velocityData.length < 2) {
      return 0;
    }
    
    // Metodo 1: Trova il momento del decollo (quando l'altezza torna a 0 o supera il baseline dopo essere stata negativa)
    let takeoffTime = null;
    let baselineHeight = trajectoryData[0]?.y || 0;
    let minHeight = Infinity;
    let minHeightIndex = -1;
    
    // Trova il minimo dell'altezza (fondo piegamento)
    for (let i = 0; i < trajectoryData.length; i++) {
      if (trajectoryData[i].y < minHeight) {
        minHeight = trajectoryData[i].y;
        minHeightIndex = i;
      }
    }
    
    // Dopo il fondo piegamento, trova quando l'altezza torna al baseline o supera (decollo)
    if (minHeightIndex >= 0) {
      for (let i = minHeightIndex + 1; i < trajectoryData.length; i++) {
        // L'altezza torna al baseline o supera il baseline e la velocità è positiva
        if (trajectoryData[i].y >= baselineHeight) {
          // Verifica che la velocità sia positiva (fase concentrica)
          const velocityAtTime = velocityData.find(v => Math.abs(v.t - trajectoryData[i].t) < 0.01);
          if (velocityAtTime && velocityAtTime.v > 0) {
            takeoffTime = trajectoryData[i].t;
            break;
          }
        }
      }
    }
    
    // Metodo 2 (più robusto): Trova l'altezza massima nella fase di volo e calcola v = sqrt(2 * g * h)
    let hMaxVolo = 0;
    if (takeoffTime !== null) {
      // Cerca l'altezza massima dopo il decollo
      for (let i = 0; i < trajectoryData.length; i++) {
        if (trajectoryData[i].t > takeoffTime && trajectoryData[i].y > hMaxVolo) {
          hMaxVolo = trajectoryData[i].y;
        }
      }
    } else {
      // Se non abbiamo trovato il decollo, cerca l'altezza massima assoluta dopo il minimo
      if (minHeightIndex >= 0) {
        for (let i = minHeightIndex + 1; i < trajectoryData.length; i++) {
          if (trajectoryData[i].y > hMaxVolo) {
            hMaxVolo = trajectoryData[i].y;
          }
        }
      }
    }
    
    // Calcola la velocità di decollo usando v = sqrt(2 * g * h)
    if (hMaxVolo > 0) {
      const hMaxM = hMaxVolo / 100; // Converti cm in metri
      const vDecolloMs = Math.sqrt(2 * g * hMaxM);
      return vDecolloMs * 100; // Converti m/s in cm/s
    }
    
    // Fallback: usa il valore diretto della velocità al momento del decollo
    if (takeoffTime !== null) {
      const velocityAtTakeoff = velocityData.find(v => Math.abs(v.t - takeoffTime) < 0.01);
      if (velocityAtTakeoff && velocityAtTakeoff.v > 0) {
        return velocityAtTakeoff.v;
      }
    }
    
    // Ultimo fallback: trova la velocità massima positiva
    let maxVelocity = 0;
    for (let i = 0; i < velocityData.length; i++) {
      if (velocityData[i].v > maxVelocity) {
        maxVelocity = velocityData[i].v;
      }
    }
    
    return maxVelocity;
  }
  
  // Funzione per calcolare la fase concentrica
  function calculateConcentricTime(trajectoryData, velocityData, bodyMassKg = 70.0) {
    if (!trajectoryData || trajectoryData.length < 2 || !velocityData || velocityData.length < 2) {
      return 0;
    }
    
    let concentricStartTime = null;
    let concentricEndTime = null;
    let baselineHeight = trajectoryData[0]?.y || 0;
    let minVelocity = Infinity;
    let minVelocityIndex = -1;
    let minHeight = Infinity;
    let minHeightIndex = -1;
    
    // Trova il minimo della velocità (fondo piegamento - fine fase eccentrica)
    for (let i = 0; i < velocityData.length; i++) {
      if (velocityData[i].v < minVelocity) {
        minVelocity = velocityData[i].v;
        minVelocityIndex = i;
      }
    }
    
    // Trova il minimo dell'altezza
    for (let i = 0; i < trajectoryData.length; i++) {
      if (trajectoryData[i].y < minHeight) {
        minHeight = trajectoryData[i].y;
        minHeightIndex = i;
      }
    }
    
    // Inizio fase concentrica: quando la velocità diventa positiva dopo il minimo
    // o quando la velocità inizia ad aumentare dopo il minimo
    if (minVelocityIndex >= 0) {
      // Cerca il punto in cui la velocità diventa positiva o inizia ad aumentare
      for (let i = minVelocityIndex; i < velocityData.length; i++) {
        // La velocità diventa positiva o inizia ad aumentare significativamente
        if (velocityData[i].v > 0 || (i > minVelocityIndex && velocityData[i].v > velocityData[i - 1].v + 5)) {
          concentricStartTime = velocityData[i].t;
          break;
        }
      }
    }
    
    // Fine fase concentrica: quando avviene il decollo (altezza torna al baseline o supera)
    if (minHeightIndex >= 0 && concentricStartTime !== null) {
      for (let i = minHeightIndex + 1; i < trajectoryData.length; i++) {
        // L'altezza torna al baseline o supera il baseline
        if (trajectoryData[i].y >= baselineHeight && trajectoryData[i].t >= concentricStartTime) {
          // Verifica che la velocità sia ancora positiva
          const velocityAtTime = velocityData.find(v => Math.abs(v.t - trajectoryData[i].t) < 0.01);
          if (velocityAtTime && velocityAtTime.v > 0) {
            concentricEndTime = trajectoryData[i].t;
            break;
          }
        }
      }
    }
    
    // Se non abbiamo trovato la fine, usa il momento della velocità massima
    if (concentricStartTime !== null && concentricEndTime === null) {
      let maxVelocity = 0;
      let maxVelocityTime = null;
      for (let i = 0; i < velocityData.length; i++) {
        if (velocityData[i].t >= concentricStartTime && velocityData[i].v > maxVelocity) {
          maxVelocity = velocityData[i].v;
          maxVelocityTime = velocityData[i].t;
        }
      }
      if (maxVelocityTime !== null) {
        concentricEndTime = maxVelocityTime;
      }
    }
    
    // Calcola il tempo della fase concentrica
    if (concentricStartTime !== null && concentricEndTime !== null && concentricEndTime > concentricStartTime) {
      return concentricEndTime - concentricStartTime;
    }
    
    return 0;
  }
  
  // Funzione per calcolare la fase eccentrica
  function calculateEccentricTime(trajectoryData, velocityData) {
    if (!trajectoryData || trajectoryData.length < 2 || !velocityData || velocityData.length < 2) {
      return 0;
    }
    
    let eccentricStartTime = null;
    let eccentricEndTime = null;
    let baselineHeight = trajectoryData[0]?.y || 0;
    let minVelocity = Infinity;
    let minVelocityIndex = -1;
    
    // Trova il minimo della velocità (fondo piegamento - fine fase eccentrica)
    for (let i = 0; i < velocityData.length; i++) {
      if (velocityData[i].v < minVelocity) {
        minVelocity = velocityData[i].v;
        minVelocityIndex = i;
      }
    }
    
    // Inizio fase eccentrica: quando la velocità diventa negativa per la prima volta
    // (l'atleta inizia a scendere)
    for (let i = 0; i < velocityData.length; i++) {
      if (velocityData[i].v < 0 && eccentricStartTime === null) {
        // Verifica anche che l'altezza stia diminuendo
        const heightAtTime = trajectoryData.find(t => Math.abs(t.t - velocityData[i].t) < 0.01);
        if (heightAtTime && heightAtTime.y < baselineHeight) {
          eccentricStartTime = velocityData[i].t;
          break;
        } else if (heightAtTime === undefined) {
          // Se non troviamo l'altezza corrispondente, usa comunque la velocità
          eccentricStartTime = velocityData[i].t;
          break;
        }
      }
    }
    
    // Fine fase eccentrica: quando la velocità raggiunge il minimo (fondo piegamento)
    if (minVelocityIndex >= 0) {
      eccentricEndTime = velocityData[minVelocityIndex].t;
    }
    
    // Calcola il tempo della fase eccentrica
    if (eccentricStartTime !== null && eccentricEndTime !== null && eccentricEndTime > eccentricStartTime) {
      return eccentricEndTime - eccentricStartTime;
    }
    
    return 0;
  }
  
  // Funzione per calcolare il tempo di contatto
  function calculateContactTime(trajectoryData, velocityData) {
    if (!trajectoryData || trajectoryData.length < 2 || !velocityData || velocityData.length < 2) {
      return 0;
    }
    
    let contactStartTime = null;
    let contactEndTime = null;
    let baselineHeight = trajectoryData[0]?.y || 0;
    
    // Inizio contatto: quando la velocità diventa negativa per la prima volta
    // (l'atleta inizia a scendere, inizia il contatto con il suolo)
    for (let i = 0; i < velocityData.length; i++) {
      if (velocityData[i].v < 0 && contactStartTime === null) {
        // Verifica anche che l'altezza stia diminuendo
        const heightAtTime = trajectoryData.find(t => Math.abs(t.t - velocityData[i].t) < 0.01);
        if (heightAtTime && heightAtTime.y < baselineHeight) {
          contactStartTime = velocityData[i].t;
          break;
        } else if (heightAtTime === undefined) {
          // Se non troviamo l'altezza corrispondente, usa comunque la velocità
          contactStartTime = velocityData[i].t;
          break;
        }
      }
    }
    
    // Fine contatto: quando avviene il decollo (altezza torna al baseline o supera)
    let minHeight = Infinity;
    let minHeightIndex = -1;
    
    // Trova il minimo dell'altezza (fondo piegamento)
    for (let i = 0; i < trajectoryData.length; i++) {
      if (trajectoryData[i].y < minHeight) {
        minHeight = trajectoryData[i].y;
        minHeightIndex = i;
      }
    }
    
    // Dopo il fondo piegamento, trova quando l'altezza torna al baseline o supera (decollo)
    if (minHeightIndex >= 0) {
      for (let i = minHeightIndex + 1; i < trajectoryData.length; i++) {
        // L'altezza torna al baseline o supera il baseline e la velocità è positiva
        if (trajectoryData[i].y >= baselineHeight) {
          // Verifica che la velocità sia positiva (fase concentrica)
          const velocityAtTime = velocityData.find(v => Math.abs(v.t - trajectoryData[i].t) < 0.01);
          if (velocityAtTime && velocityAtTime.v > 0) {
            contactEndTime = trajectoryData[i].t;
            break;
          }
        }
      }
    }
    
    // Se non abbiamo trovato il decollo, usa il momento della velocità massima
    if (contactStartTime !== null && contactEndTime === null) {
      let maxVelocity = 0;
      let maxVelocityTime = null;
      for (let i = 0; i < velocityData.length; i++) {
        if (velocityData[i].t >= contactStartTime && velocityData[i].v > maxVelocity) {
          maxVelocity = velocityData[i].v;
          maxVelocityTime = velocityData[i].t;
        }
      }
      if (maxVelocityTime !== null) {
        contactEndTime = maxVelocityTime;
      }
    }
    
    // Calcola il tempo di contatto
    if (contactStartTime !== null && contactEndTime !== null && contactEndTime > contactStartTime) {
      return contactEndTime - contactStartTime;
    }
    
    // Fallback: usa la somma di fase eccentrica + fase concentrica
    const eccentricTime = calculateEccentricTime(trajectoryData, velocityData);
    const concentricTime = calculateConcentricTime(trajectoryData, velocityData, 70.0);
    if (eccentricTime > 0 && concentricTime > 0) {
      return eccentricTime + concentricTime;
    }
    
    return 0;
  }
  
  // Funzione per calcolare la potenza esplosiva
  function calculateEstimatedPower(velocityData, trajectoryData, bodyMassKg = 70.0) {
    if (!velocityData || velocityData.length < 2 || bodyMassKg <= 0) {
      return 0;
    }
    
    // Identifica la fase di contatto: quando l'altezza è vicina a 0 o negativa
    const CONTACT_THRESHOLD = 5.0; // cm - soglia per considerare l'atleta a contatto con il suolo
    
    // Crea una mappa per l'altezza per accesso rapido
    const heightMap = new Map();
    if (trajectoryData && trajectoryData.length > 0) {
      trajectoryData.forEach(point => {
        heightMap.set(point.t, point.y);
      });
    }
    
    // Calcola l'accelerazione dalla velocità
    const accelerations = [];
    for (let i = 1; i < velocityData.length; i++) {
      const prev = velocityData[i - 1];
      const curr = velocityData[i];
      const deltaT = curr.t - prev.t;
      
      if (deltaT > 0 && isFinite(deltaT)) {
        // Velocità in m/s
        const v1_ms = prev.v / 100;
        const v2_ms = curr.v / 100;
        const a_ms2 = (v2_ms - v1_ms) / deltaT;
        
        accelerations.push({
          time: curr.t,
          a_ms2: a_ms2,
          velocity: curr.v
        });
      }
    }
    
    if (accelerations.length === 0) {
      return 0;
    }
    
    // Calcola la potenza istantanea solo durante la fase concentrica (velocità positiva)
    const powers = [];
    
    for (let i = 0; i < accelerations.length; i++) {
      const acc = accelerations[i];
      const height = heightMap.get(acc.time);
      
      // Considera solo i punti durante il contatto (altezza <= CONTACT_THRESHOLD)
      // e durante la fase concentrica (velocità positiva)
      const isInContact = height !== undefined && Math.abs(height) <= CONTACT_THRESHOLD;
      
      if (isInContact && acc.velocity > 0 && Math.abs(acc.a_ms2) > 0.05) { // Soglia per filtrare il rumore
        // Forza: F = m * (a + g)
        // Durante il contatto, la forza totale è m * (a + g) dove a è l'accelerazione verso l'alto
        const force = bodyMassKg * (acc.a_ms2 + g);
        
        // Considera solo forze positive significative (verso l'alto, durante la fase concentrica)
        if (force > bodyMassKg * g * 0.3) {
          // Potenza: P = F * v
          // v in m/s
          const v_ms = acc.velocity / 100;
          const power = force * v_ms;
          
          if (power > 0) {
            powers.push(power);
          }
        }
      }
    }
    
    if (powers.length === 0) {
      return 0;
    }
    
    // Trova il picco massimo della potenza
    const maxPower = Math.max(...powers);
    
    return maxPower;
  }
  
  // La funzione getPhaseTimes() è stata rimossa - ora usa phaseTimes dal backend
  
  // Tutti i calcoli sono ora fatti nel backend e arrivano tramite results
  
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

  $: if (combinedCanvas) {
    if ($appState.trajectoryData.length > 0 && derivedVelocityData.length > 0) {
      drawCombinedChart();
    } else {
      clearCanvas(combinedCanvas, TRAJECTORY_STYLE.background);
    }
  }

  // Reattività per ridisegnare i grafici fullscreen quando si aprono
  $: if (fullscreenChart === 'trajectory' && fullscreenTrajectoryCanvas && $appState.trajectoryData.length > 0) {
    const width = Math.floor(window.innerWidth * 0.9);
    const height = Math.floor(window.innerHeight * 0.8);
    drawTrajectoryChart(fullscreenTrajectoryCanvas, width, height);
  }

  $: if (fullscreenChart === 'velocity' && fullscreenVelocityCanvas && derivedVelocityData.length > 0) {
    const width = Math.floor(window.innerWidth * 0.9);
    const height = Math.floor(window.innerHeight * 0.8);
    drawVelocityChart(fullscreenVelocityCanvas, width, height);
  }

  $: if (fullscreenChart === 'combined' && fullscreenCombinedCanvas && $appState.trajectoryData.length > 0 && derivedVelocityData.length > 0) {
    const width = Math.floor(window.innerWidth * 0.9);
    const height = Math.floor(window.innerHeight * 0.8);
    drawCombinedChart(fullscreenCombinedCanvas, width, height);
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

    // Aggiungi un punto iniziale a t=0 (primo tempo disponibile) con v=0
    return [{ t: data[0].t, v: 0 }, ...velocities];
  }
  
  function drawTrajectoryChart(canvas = null, customWidth = null, customHeight = null) {
    const targetCanvas = canvas || trajectoryCanvas;
    if (!targetCanvas) return;
    
    const ctx = targetCanvas.getContext('2d');
    const width = customWidth || targetCanvas.width;
    const height = customHeight || targetCanvas.height;
    
    // Imposta le dimensioni se sono state specificate
    if (customWidth) targetCanvas.width = customWidth;
    if (customHeight) targetCanvas.height = customHeight;
    const padding = 52;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    clearCanvas(targetCanvas, TRAJECTORY_STYLE.background);
    
    const data = $appState.trajectoryData;
    if (data.length === 0) return;
    
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxY = Math.max(...data.map(d => d.y));
    const minY = Math.min(...data.map(d => d.y));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaY = maxY === minY ? 1 : (maxY - minY);
    
    // Usa i tempi delle fasi dal backend
    const currentPhaseTimes = phaseTimes;
    
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
    
    // Disegna le aree colorate per le fasi (sotto la linea)
    if (phaseTimes) {
      // Area fase eccentrica
      if (currentPhaseTimes.eccentricStart !== null && currentPhaseTimes.eccentricEnd !== null) {
        const x1 = padding + ((currentPhaseTimes.eccentricStart - minT) / deltaT) * chartWidth;
        const x2 = padding + ((currentPhaseTimes.eccentricEnd - minT) / deltaT) * chartWidth;
        ctx.fillStyle = 'rgba(255, 165, 0, 0.15)';
        ctx.fillRect(x1, padding, x2 - x1, chartHeight);
      }
      
      // Area fase concentrica
      if (currentPhaseTimes.concentricStart !== null && currentPhaseTimes.concentricEnd !== null) {
        const x1 = padding + ((currentPhaseTimes.concentricStart - minT) / deltaT) * chartWidth;
        const x2 = padding + ((currentPhaseTimes.concentricEnd - minT) / deltaT) * chartWidth;
        ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
        ctx.fillRect(x1, padding, x2 - x1, chartHeight);
      }
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
    
    // Disegna le linee di riferimento per le fasi
    if (currentPhaseTimes) {
      const markerColors = {
        contact: 'rgba(255, 255, 0, 0.7)',      // Giallo per contatto
        eccentric: 'rgba(255, 165, 0, 0.7)',   // Arancione per eccentrica
        concentric: 'rgba(0, 255, 0, 0.7)',     // Verde per concentrica
        takeoff: 'rgba(255, 0, 0, 0.7)'        // Rosso per decollo
      };
      
      // Linea inizio contatto / inizio eccentrica
      if (currentPhaseTimes.contactStart !== null) {
        const x = padding + ((currentPhaseTimes.contactStart - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.contact;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.contact;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Inizio Contatto', x, padding + 2);
      }
      
      // Linea fine eccentrica / inizio concentrica
      if (currentPhaseTimes.eccentricEnd !== null) {
        const x = padding + ((currentPhaseTimes.eccentricEnd - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.eccentric;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.eccentric;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Fine Eccentrica', x, padding + 14);
      }
      
      // Linea decollo / fine concentrica
      if (currentPhaseTimes.takeoff !== null) {
        const x = padding + ((currentPhaseTimes.takeoff - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.takeoff;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.takeoff;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Decollo', x, padding + 26);
      }
    }
    
    drawLabels(ctx, {
      width,
      height,
      padding,
      xText: 'Tempo (s)',
      yText: 'Altezza (cm)',
      style: TRAJECTORY_STYLE
    });
  }
  
  function drawVelocityChart(canvas = null, customWidth = null, customHeight = null) {
    const targetCanvas = canvas || velocityCanvas;
    if (!targetCanvas) return;
    
    const ctx = targetCanvas.getContext('2d');
    const width = customWidth || targetCanvas.width;
    const height = customHeight || targetCanvas.height;
    
    // Imposta le dimensioni se sono state specificate
    if (customWidth) targetCanvas.width = customWidth;
    if (customHeight) targetCanvas.height = customHeight;
    const padding = 52;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    clearCanvas(targetCanvas, VELOCITY_STYLE.background);
    
    const data = derivedVelocityData;
    if (data.length === 0) return;
    
    const maxT = Math.max(...data.map(d => d.t));
    const minT = Math.min(...data.map(d => d.t));
    const maxV = Math.max(...data.map(d => d.v));
    const minV = Math.min(...data.map(d => d.v));
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    const deltaV = maxV === minV ? (Math.abs(maxV) || 1) : (maxV - minV);
    
    // Usa i tempi delle fasi dal backend
    const currentPhaseTimes = phaseTimes;
    
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
      invertYLabel: true,
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
    
    // Disegna le aree colorate per le fasi (sotto la linea)
    if (phaseTimes) {
      // Area fase eccentrica
      if (currentPhaseTimes.eccentricStart !== null && currentPhaseTimes.eccentricEnd !== null) {
        const x1 = padding + ((currentPhaseTimes.eccentricStart - minT) / deltaT) * chartWidth;
        const x2 = padding + ((currentPhaseTimes.eccentricEnd - minT) / deltaT) * chartWidth;
        ctx.fillStyle = 'rgba(255, 165, 0, 0.15)';
        ctx.fillRect(x1, padding, x2 - x1, chartHeight);
      }
      
      // Area fase concentrica
      if (currentPhaseTimes.concentricStart !== null && currentPhaseTimes.concentricEnd !== null) {
        const x1 = padding + ((currentPhaseTimes.concentricStart - minT) / deltaT) * chartWidth;
        const x2 = padding + ((currentPhaseTimes.concentricEnd - minT) / deltaT) * chartWidth;
        ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
        ctx.fillRect(x1, padding, x2 - x1, chartHeight);
      }
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
    
    // Disegna le linee di riferimento per le fasi
    if (currentPhaseTimes) {
      const markerColors = {
        contact: 'rgba(255, 255, 0, 0.7)',      // Giallo per contatto
        eccentric: 'rgba(255, 165, 0, 0.7)',   // Arancione per eccentrica
        concentric: 'rgba(0, 255, 0, 0.7)',     // Verde per concentrica
        takeoff: 'rgba(255, 0, 0, 0.7)'        // Rosso per decollo
      };
      
      // Linea inizio contatto / inizio eccentrica
      if (currentPhaseTimes.contactStart !== null) {
        const x = padding + ((currentPhaseTimes.contactStart - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.contact;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.contact;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Inizio Contatto', x, padding + 2);
      }
      
      // Linea fine eccentrica / inizio concentrica
      if (currentPhaseTimes.eccentricEnd !== null) {
        const x = padding + ((currentPhaseTimes.eccentricEnd - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.eccentric;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.eccentric;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Fine Eccentrica', x, padding + 14);
      }
      
      // Linea decollo / fine concentrica
      if (currentPhaseTimes.takeoff !== null) {
        const x = padding + ((currentPhaseTimes.takeoff - minT) / deltaT) * chartWidth;
        ctx.strokeStyle = markerColors.takeoff;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Etichetta
        ctx.fillStyle = markerColors.takeoff;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Decollo', x, padding + 26);
      }
    }
    
    drawLabels(ctx, {
      width,
      height,
      padding,
      xText: 'Tempo (s)',
      yText: 'Velocità (cm/s)',
      style: VELOCITY_STYLE
    });
  }

  function drawCombinedChart(canvas = null, customWidth = null, customHeight = null) {
    const targetCanvas = canvas || combinedCanvas;
    if (!targetCanvas) return;
    
    const ctx = targetCanvas.getContext('2d');
    const width = customWidth || targetCanvas.width;
    const height = customHeight || targetCanvas.height;
    
    // Imposta le dimensioni
    if (customWidth) targetCanvas.width = customWidth;
    if (customHeight) targetCanvas.height = customHeight;
    
    const padding = 52;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    clearCanvas(targetCanvas, TRAJECTORY_STYLE.background);
    
    const trajectoryData = $appState.trajectoryData;
    const velocityData = derivedVelocityData;
    
    if (trajectoryData.length === 0 || velocityData.length === 0) return;
    
    // --- 1. Calcolo Range Temporale (Asse X) ---
    const allTimes = [...trajectoryData.map(d => d.t), ...velocityData.map(d => d.t)];
    const maxT = Math.max(...allTimes);
    const minT = Math.min(...allTimes);
    const deltaT = maxT === minT ? 1 : (maxT - minT);
    
    // --- 2. Calcolo Range Iniziali (Asse Y) ---
    
    // Altezza (Trajectory)
    const rawMaxY = Math.max(...trajectoryData.map(d => d.y));
    const rawMinY = Math.min(...trajectoryData.map(d => d.y));
    
    // Velocità (Velocity)
    const rawMaxV = Math.max(...velocityData.map(d => d.v));
    const rawMinV = Math.min(...velocityData.map(d => d.v));
    
    // --- 3. LOGICA ALLINEAMENTO ZERI (Sync Zero Points) ---
    
    let finalMinY = rawMinY;
    let finalMaxY = rawMaxY;
    let finalMinV = rawMinV;
    let finalMaxV = rawMaxV;
    
    // Calcoliamo i range attuali
    const rangeY = rawMaxY - rawMinY || 1;
    const rangeV = rawMaxV - rawMinV || 1;
    
    // Calcoliamo la "percentuale di negativo" necessaria per ciascun grafico
    // Esempio: Se v va da -100 a 300, il rapporto è |-100| / 400 = 0.25 (25% di spazio sotto lo zero)
    // Usiamo Math.abs per sicurezza sui minimi
    const ratioBelowY = (rawMinY < 0 || rawMaxY < 0) ? Math.abs(rawMinY) / rangeY : 0;
    const ratioBelowV = (rawMinV < 0 || rawMaxV < 0) ? Math.abs(rawMinV) / rangeV : 0;
    
    // Confrontiamo chi ha bisogno di più spazio sotto lo zero
    if (ratioBelowV > ratioBelowY) {
        // La velocità domina (ha più negativo). 
        // Dobbiamo abbassare fittiziamente il minimo dell'altezza per alzare il suo zero.
        // Formula: NewMin = -(RatioDominante * MaxAttuale) / (1 - RatioDominante)
        // Semplificazione algebrica per mantenere la proporzione:
        finalMinY = - (ratioBelowV * rawMaxY) / (1 - ratioBelowV);
    } else if (ratioBelowY > ratioBelowV) {
        // L'altezza domina (caso raro nel salto, ma possibile).
        // Adattiamo la velocità.
        finalMinV = - (ratioBelowY * rawMaxV) / (1 - ratioBelowY);
    }
    
    // Calcolo Delta Finali Sincronizzati
    const deltaY = finalMaxY - finalMinY;
    const deltaV = finalMaxV - finalMinV;
    
    // --- 4. Funzioni di Normalizzazione Sincronizzate ---
    
    const normalizeTrajectory = (heightValue) => {
        if (typeof heightValue !== 'number' || !isFinite(heightValue)) return 0;
        return (heightValue - finalMinY) / deltaY;
    };

    const normalizeVelocity = (velocityValue) => {
        if (typeof velocityValue !== 'number' || !isFinite(velocityValue)) return 0;
        return (velocityValue - finalMinV) / deltaV;
    };
    
    const currentPhaseTimes = phaseTimes;
    
    // --- 5. Disegno Griglie ---
    
    // Griglia Sinistra (Altezza) - Usa finalMinY e deltaY
    drawGrid(ctx, {
        padding,
        width,
        height,
        chartWidth,
        chartHeight,
        minT,
        deltaT,
        minY: finalMinY, // IMPORTANTE: Passare i valori sincronizzati
        deltaY: deltaY,
        style: TRAJECTORY_STYLE,
        xFormatter: (value) => value.toFixed(2),
        yFormatter: (value) => value.toFixed(1)
    });
    
    // Etichette Destra (Velocità) - Usa finalMinV e deltaV
    ctx.strokeStyle = VELOCITY_STYLE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = VELOCITY_STYLE.label;
    ctx.font = '11px sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    
    for (let i = 0; i <= GRID_STEPS; i++) {
        const ratio = i / GRID_STEPS;
        const y = padding + (chartHeight * ratio);
        // Calcola il valore basandosi sul range sincronizzato
        const value = finalMinV + (deltaV * (GRID_STEPS - i) / GRID_STEPS);
        
        // Disegna solo il testo, le righe orizzontali sono già fatte da drawGrid
        // e coincidono perfettamente grazie all'allineamento degli zeri
        const label = value.toFixed(1);
        ctx.fillText(label, width - padding + 12, y);
    }
    
    // --- 6. Linea Zero Comune ---
    // Dato che abbiamo sincronizzato, basta calcolarne una.
    // Se lo zero rientra nel grafico, lo disegniamo.
    if ((finalMinY <= 0 && finalMaxY >= 0) || (finalMinV <= 0 && finalMaxV >= 0)) {
        // Calcola la Y dello zero (sarà identica per Trajectory e Velocity)
        const zeroY = height - padding - normalizeTrajectory(0) * chartHeight;
        
        // Controllo di sicurezza per non disegnare fuori dal chart area
        if (zeroY >= padding && zeroY <= height - padding) {
            ctx.strokeStyle = '#AAAAAA'; // Colore neutro per lo zero comune
            ctx.lineWidth = 1.5;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(padding, zeroY);
            ctx.lineTo(width - padding, zeroY);
            ctx.stroke();
            ctx.setLineDash([]);
        }
    }
    
    // --- 7. Aree Fasi ---
    if (phaseTimes) {
        const drawPhaseRect = (start, end, color) => {
            if (start !== null && end !== null) {
                const x1 = padding + ((start - minT) / deltaT) * chartWidth;
                const x2 = padding + ((end - minT) / deltaT) * chartWidth;
                ctx.fillStyle = color;
                ctx.fillRect(x1, padding, x2 - x1, chartHeight);
            }
        };
        
        drawPhaseRect(currentPhaseTimes.eccentricStart, currentPhaseTimes.eccentricEnd, 'rgba(255, 165, 0, 0.15)');
        drawPhaseRect(currentPhaseTimes.concentricStart, currentPhaseTimes.concentricEnd, 'rgba(0, 255, 0, 0.15)');
    }
    
    // --- 8. Disegno Curve ---
    
    // Traiettoria (Altezza)
    ctx.lineWidth = 3;
    ctx.strokeStyle = TRAJECTORY_STYLE.line;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = TRAJECTORY_STYLE.lineShadow;
    ctx.shadowBlur = 12;
    
    ctx.beginPath();
    trajectoryData.forEach((point, i) => {
        const x = padding + ((point.t - minT) / deltaT) * chartWidth;
        const val = (point && typeof point.y === 'number') ? point.y : 0;
        const y = height - padding - normalizeTrajectory(val) * chartHeight;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;
    
    // Velocità
    ctx.lineWidth = 3;
    ctx.strokeStyle = VELOCITY_STYLE.line;
    ctx.shadowColor = VELOCITY_STYLE.lineShadow;
    ctx.shadowBlur = 12;
    
    ctx.beginPath();
    velocityData.forEach((point, i) => {
        const x = padding + ((point.t - minT) / deltaT) * chartWidth;
        const y = height - padding - normalizeVelocity(point.v) * chartHeight;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;
    
    // --- 9. Punti di Campionamento ---
    
    // Punti Traiettoria
    ctx.fillStyle = TRAJECTORY_STYLE.line;
    trajectoryData.forEach((point, i) => {
        if (i % Math.max(1, Math.floor(trajectoryData.length / 25)) === 0 || i === trajectoryData.length - 1) {
            const x = padding + ((point.t - minT) / deltaT) * chartWidth;
            const val = (point && typeof point.y === 'number') ? point.y : 0;
            const y = height - padding - normalizeTrajectory(val) * chartHeight;
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        }
    });
    
    // Punti Velocità
    ctx.fillStyle = VELOCITY_STYLE.line;
    velocityData.forEach((point, i) => {
        if (i % Math.max(1, Math.floor(velocityData.length / 25)) === 0 || i === velocityData.length - 1) {
            const x = padding + ((point.t - minT) / deltaT) * chartWidth;
            const y = height - padding - normalizeVelocity(point.v) * chartHeight;
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        }
    });
    
    // --- 10. Linee Verticali Fasi (Marker) ---
    if (currentPhaseTimes) {
        const drawPhaseLine = (time, label, color, yOffsetLabel) => {
            if (time !== null) {
                const x = padding + ((time - minT) / deltaT) * chartWidth;
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, height - padding);
                ctx.stroke();
                ctx.setLineDash([]);
                
                ctx.fillStyle = color;
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(label, x, padding + yOffsetLabel);
            }
        };
        
        const colors = {
            contact: 'rgba(255, 255, 0, 0.7)',
            eccentric: 'rgba(255, 165, 0, 0.7)',
            takeoff: 'rgba(255, 0, 0, 0.7)'
        };
        
        drawPhaseLine(currentPhaseTimes.contactStart, 'Inizio Contatto', colors.contact, 2);
        drawPhaseLine(currentPhaseTimes.eccentricEnd, 'Fine Eccentrica', colors.eccentric, 14);
        drawPhaseLine(currentPhaseTimes.takeoff, 'Decollo', colors.takeoff, 26);
    }
    
    // --- 11. Etichette Assi ---
    ctx.fillStyle = TRAJECTORY_STYLE.label;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText('Tempo (s)', width / 2, height - 18);
    
    // Label Asse Y Sinistro
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillStyle = TRAJECTORY_STYLE.label;
    ctx.fillText('Altezza (cm)', 0, 0);
    ctx.restore();
    
    // Label Asse Y Destro
    ctx.save();
    ctx.translate(width - 20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillStyle = VELOCITY_STYLE.label;
    ctx.fillText('Velocità (cm/s)', 0, 0);
    ctx.restore();
}

  function clearCanvas(canvas, background) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function openFullscreenChart(chartType) {
    fullscreenChart = chartType;
    // Ridisegna il grafico a dimensioni maggiori dopo che il DOM è aggiornato
    setTimeout(() => {
      const width = Math.floor(window.innerWidth * 0.9);
      const height = Math.floor(window.innerHeight * 0.8);
      
      if (chartType === 'trajectory' && fullscreenTrajectoryCanvas) {
        drawTrajectoryChart(fullscreenTrajectoryCanvas, width, height);
      } else if (chartType === 'velocity' && fullscreenVelocityCanvas) {
        drawVelocityChart(fullscreenVelocityCanvas, width, height);
      } else if (chartType === 'combined' && fullscreenCombinedCanvas) {
        drawCombinedChart(fullscreenCombinedCanvas, width, height);
      }
    }, 100);
  }

  function closeFullscreenChart() {
    fullscreenChart = null;
  }

  // Gestione tasto ESC per chiudere il modal
  function handleKeydown(event) {
    if (event.key === 'Escape' && fullscreenChart) {
      closeFullscreenChart();
    }
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

<div class="results-container bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700 h-full flex flex-col" role="region" aria-label="Risultati analisi salto">
  <div class="results-header bg-gradient-to-r from-green-600 to-teal-600 px-4 sm:px-6 py-3 sm:py-4">
    <h2 class="text-lg sm:text-xl font-semibold text-white">Risultati Analisi</h2>
    <p class="text-green-100 text-xs sm:text-sm mt-1">Analisi completata con successo</p>
  </div>
  
  <div class="results-content p-4 sm:p-6 space-y-4 sm:space-y-6 flex-1 overflow-auto">
    <!-- Main Metrics -->
    <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Metriche principali">
      <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Metriche Principali</h3>
      <div class="grid grid-cols-2 gap-3 sm:gap-4" role="list">
        <div role="listitem">
          <p class="text-xs text-slate-400 mb-1">Altezza Max</p>
          <p class="text-xl sm:text-2xl font-bold text-green-400" aria-live="polite">{results.max_height} cm</p>
        </div>
        <div role="listitem">
          <p class="text-xs text-slate-400 mb-1">Tempo di Volo</p>
          <p class="text-xl sm:text-2xl font-bold text-blue-400" aria-live="polite">{results.flight_time} s</p>
        </div>
        <div role="listitem">
          <p class="text-xs text-slate-400 mb-1">Velocità Decollo</p>
          <p class="text-xl sm:text-2xl font-bold text-purple-400" aria-live="polite">
            {(results.calculated_takeoff_velocity || results.takeoff_velocity || 0)} cm/s
          </p>
        </div>
        <div role="listitem">
          <p class="text-xs text-slate-400 mb-1">Potenza Est.</p>
          <p class="text-xl sm:text-2xl font-bold text-yellow-400" aria-live="polite">
            {(results.calculated_estimated_power || results.estimated_power || 0)} W
          </p>
        </div>
      </div>
    </div>
    
    <!-- Phase Timing -->
    <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Analisi fasi">
      <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Analisi Fasi</h3>
      <div class="space-y-2.5 sm:space-y-3" role="list">
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Tempo Contatto</span>
          <span class="text-base sm:text-lg font-semibold text-white" aria-live="polite">
            {(results.calculated_contact_time || results.contact_time || 0)} s
          </span>
        </div>
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Fase Eccentrica</span>
          <span class="text-base sm:text-lg font-semibold text-white" aria-live="polite">
            {(results.calculated_eccentric_time || results.eccentric_time || 0)} s
          </span>
        </div>
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Fase Concentrica</span>
          <span class="text-base sm:text-lg font-semibold text-white" aria-live="polite">
            {(results.calculated_concentric_time || results.concentric_time || 0)} s
          </span>
        </div>
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Tempo Caduta</span>
          <span class="text-base sm:text-lg font-semibold text-white" aria-live="polite">{results.fall_time} s</span>
        </div>
      </div>
    </div>
    
    <!-- Biomechanical Parameters -->
    <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Parametri biomeccanici">
      <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Parametri Biomeccanici</h3>
      <div class="space-y-2.5 sm:space-y-3" role="list">
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Forza Media</span>
          <span class="text-base sm:text-lg font-semibold text-white" aria-live="polite">
            {(results.calculated_average_force || results.average_force || 0)} N
          </span>
        </div>
        <div class="flex justify-between items-center" role="listitem">
          <span class="text-xs sm:text-sm text-slate-400">Salto Rilevato</span>
          <span class="text-base sm:text-lg font-semibold {results.jump_detected ? 'text-green-400' : 'text-red-400'}" aria-live="polite">
            {results.jump_detected ? 'Sì' : 'No'}
          </span>
        </div>
      </div>
    </div>
    
    <!-- Trajectory Chart -->
    {#if $appState.trajectoryData.length > 0}
      <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Grafico traiettoria">
        <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Traiettoria del Salto</h3>
        <canvas
          bind:this={trajectoryCanvas}
          width="400"
          height="250"
          class="w-full rounded-lg cursor-pointer hover:opacity-90 focus:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          on:click={() => openFullscreenChart('trajectory')}
          role="button"
          tabindex="0"
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && openFullscreenChart('trajectory')}
          aria-label="Grafico traiettoria del salto. Clicca per ingrandire"
        ></canvas>
      </div>
    {/if}
    
    <!-- Velocity Chart -->
    {#if derivedVelocityData.length > 0}
      <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Grafico velocità">
        <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Velocità nel Tempo</h3>
        <canvas
          bind:this={velocityCanvas}
          width="400"
          height="250"
          class="w-full rounded-lg cursor-pointer hover:opacity-90 focus:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          on:click={() => openFullscreenChart('velocity')}
          role="button"
          tabindex="0"
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && openFullscreenChart('velocity')}
          aria-label="Grafico velocità nel tempo. Clicca per ingrandire"
        ></canvas>
      </div>
    {/if}
    
    <!-- Combined Chart -->
    {#if $appState.trajectoryData.length > 0 && derivedVelocityData.length > 0}
      <div class="bg-slate-900/50 rounded-xl p-4 sm:p-5 border border-slate-700" role="region" aria-label="Grafico confronto">
        <h3 class="text-xs sm:text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3 sm:mb-4">Confronto Traiettoria e Velocità</h3>
        <canvas
          bind:this={combinedCanvas}
          width="400"
          height="250"
          class="w-full rounded-lg cursor-pointer hover:opacity-90 focus:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          on:click={() => openFullscreenChart('combined')}
          role="button"
          tabindex="0"
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && openFullscreenChart('combined')}
          aria-label="Grafico confronto traiettoria e velocità. Clicca per ingrandire"
        ></canvas>
      </div>
    {/if}
    
    <!-- Save message -->
    {#if saveMessage}
      <div class="bg-blue-500/10 border border-blue-500/50 rounded-lg p-3 sm:p-4" role="status" aria-live="polite">
        <p class="text-blue-400 text-sm">{saveMessage}</p>
      </div>
    {/if}
    
    <!-- Actions -->
    <div class="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-3 sm:pt-4">
      <button
        on:click={saveResults}
        disabled={isSaving}
        class="flex-1 bg-gradient-to-r from-green-600 to-teal-600 text-white px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg font-semibold hover:from-green-700 hover:to-teal-700 focus:from-green-700 focus:to-teal-700 transition-all duration-200 shadow-lg hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label={isSaving ? 'Salvataggio in corso' : 'Salva risultati analisi'}
      >
        <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        {isSaving ? 'Salvataggio...' : 'Salva Risultati'}
      </button>
      <button
        on:click={handleReset}
        class="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 focus:from-blue-700 focus:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-800"
        aria-label="Avvia una nuova analisi"
      >
        <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Nuova Analisi
      </button>
    </div>
  </div>
  
  <!-- Fullscreen Chart Modal -->
  {#if fullscreenChart}
    <div 
      class="fixed inset-0 bg-black/90 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="fullscreen-chart-title"
      on:click|self={closeFullscreenChart}
      on:keydown={(e) => e.key === 'Escape' && closeFullscreenChart()}
    >
      <div 
        class="relative bg-slate-900 rounded-xl p-4 sm:p-6 max-w-[95vw] max-h-[95vh] overflow-auto z-10 shadow-2xl border border-slate-700"
      >
        <!-- Close button -->
        <button
          on:click={closeFullscreenChart}
          class="absolute top-3 sm:top-4 right-3 sm:right-4 text-white hover:text-red-400 focus:text-red-400 transition-colors z-10 bg-slate-800 rounded-full p-2 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          aria-label="Chiudi grafico a schermo intero"
        >
          <svg class="w-5 sm:w-6 h-5 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        
        <!-- Chart title -->
        <h3 id="fullscreen-chart-title" class="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 pr-10">
          {#if fullscreenChart === 'trajectory'}
            Traiettoria del Salto
          {:else if fullscreenChart === 'velocity'}
            Velocità nel Tempo
          {:else if fullscreenChart === 'combined'}
            Confronto Traiettoria e Velocità
          {/if}
        </h3>
        
        <!-- Fullscreen canvas -->
        {#if fullscreenChart === 'trajectory'}
          <canvas
            bind:this={fullscreenTrajectoryCanvas}
            class="rounded-lg"
          ></canvas>
        {:else if fullscreenChart === 'velocity'}
          <canvas
            bind:this={fullscreenVelocityCanvas}
            class="rounded-lg"
          ></canvas>
        {:else if fullscreenChart === 'combined'}
          <canvas
            bind:this={fullscreenCombinedCanvas}
            class="rounded-lg"
          ></canvas>
        {/if}
      </div>
    </div>
  {/if}
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