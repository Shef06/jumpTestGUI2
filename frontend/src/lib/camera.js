export async function enumerateCameras() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    throw new Error('API mediaDevices non disponibile');
  }
  let tempStream = null;
  try {
    // Sblocca label e deviceId su alcuni browser
    tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  } catch (_) {
    // L'utente può concedere in seguito
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoInputs = devices.filter(d => d.kind === 'videoinput');
    return videoInputs;
  } finally {
    if (tempStream) {
      try { tempStream.getTracks().forEach(t => t.stop()); } catch (_) {}
    }
  }
}

export async function openPreviewByIndex(index, videoInputs) {
  const list = Array.isArray(videoInputs) ? videoInputs : [];
  const chosen = list[index] || list[0];
  if (chosen && chosen.deviceId) {
    return await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: chosen.deviceId } }, audio: false });
  }
  // Fallback
  return await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
}

export function stopStream(stream) {
  try { stream?.getTracks()?.forEach(t => t.stop()); } catch (_) {}
}



