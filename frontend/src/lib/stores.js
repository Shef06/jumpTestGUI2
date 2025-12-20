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
    const testId = typeof window !== 'undefined' ? sessionStorage.getItem('testId') : null;
    if (testId) {
      const jumpTestId = `${testId}_jump_${newJump.id}`;
      try {
        await api.saveResults(jumpTestId, {
          results: newJump,
          trajectory: jumpData.trajectory || [],
          velocity: jumpData.velocity || [],
          settings: {
            mass: jumpData.body_mass_kg || 75,
            fps: jumpData.fps || 30
          }
        });
      } catch (error) {
        console.error('Errore nel salvataggio automatico:', error);
      }
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