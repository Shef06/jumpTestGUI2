import { writable } from 'svelte/store';

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