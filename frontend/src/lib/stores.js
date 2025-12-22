import { writable } from 'svelte/store';
import { api } from './api.js';

export const appState = writable({
  isAnalyzing: false,
  isRecording: false,
  isCalibrating: false,
  isPaused: false,
  isCameraPreview: false,
  previewStream: null,
  inputMode: 'none', // 'none' | 'upload' | 'camera'
  videoFrame: null,
  realtimeData: {},
  trajectoryData: [],
  velocityData: [],
  localVideoUrl: null
});

export function updateVideoFrame(frame) {
  appState.update(state => ({
    ...state,
    videoFrame: frame
  }));
}

export function updateRealtimeData(realtime, trajectory, velocity) {
  appState.update(state => ({
    ...state,
    realtimeData: realtime,
    trajectoryData: trajectory || state.trajectoryData,
    velocityData: velocity || state.velocityData
  }));
}

export function setLocalVideoUrl(url) {
  appState.update(state => ({
    ...state,
    localVideoUrl: url
  }));
}

export function clearLocalVideoUrl() {
  appState.update(state => ({
    ...state,
    localVideoUrl: null
  }));
}

export function setCameraPreview(isOn) {
  appState.update(state => ({
    ...state,
    isCameraPreview: !!isOn
  }));
}

export function setPreviewStream(stream) {
  appState.update(state => ({
    ...state,
    previewStream: stream || null
  }));
}

export function clearPreviewStream() {
  appState.update(state => ({
    ...state,
    previewStream: null
  }));
}

export function setInputMode(mode) {
  appState.update(state => ({
    ...state,
    inputMode: mode === 'upload' || mode === 'camera' ? mode : 'none'
  }));
}

// Store per la sessione di salti
export const sessionStore = writable({
  jumps: [],
  currentJumpIndex: 0,
  selectedJumpIds: []
});

export async function addJumpToSession(jumpData) {
  let newJump;
  sessionStore.update(state => {
    newJump = {
      ...jumpData,
      id: state.jumps.length + 1,
      timestamp: Date.now()
    };
    const newJumps = [...state.jumps, newJump];
    const newSelectedIds = jumpData.jump_detected 
      ? [...state.selectedJumpIds, newJump.id]
      : state.selectedJumpIds;
    
    return {
      jumps: newJumps,
      currentJumpIndex: newJumps.length - 1,
      selectedJumpIds: newSelectedIds
    };
  });
  
  // Salva automaticamente quando viene aggiunto un salto
  if (newJump && newJump.jump_detected) {
    let testId = typeof window !== 'undefined' ? sessionStorage.getItem('testId') : null;
    
    // Genera un testId se non esiste
    if (!testId && typeof window !== 'undefined') {
      testId = `test_${Date.now()}`;
      sessionStorage.setItem('testId', testId);
      console.log('testId generato automaticamente:', testId);
    }
    
    if (testId) {
      try {
        console.log('Salvataggio automatico salto:', testId, newJump.id, newJump);
        const result = await api.saveResults(testId, {
          results: newJump,
          trajectory: jumpData.trajectory || newJump.trajectory || [],
          velocity: jumpData.velocity || newJump.velocity || [],
          settings: {
            mass: jumpData.body_mass_kg || newJump.body_mass_kg || 75,
            fps: jumpData.fps || newJump.fps || 30
          }
        }, newJump.id, 'add');
        console.log('Salvataggio completato:', result);
      } catch (error) {
        console.error('Errore nel salvataggio automatico:', error);
      }
    } else {
      console.warn('testId non disponibile, salvataggio saltato');
    }
  }
}

export function clearSession() {
  sessionStore.set({
    jumps: [],
    currentJumpIndex: 0,
    selectedJumpIds: []
  });
}