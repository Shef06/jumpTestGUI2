import { writable } from 'svelte/store';

export const appState = writable({
  isAnalyzing: false,
  isRecording: false,
  isCalibrating: false,
  isPaused: false,
  videoFrame: null,
  realtimeData: {},
  trajectoryData: [],
  velocityData: []
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