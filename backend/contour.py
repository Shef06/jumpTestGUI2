import cv2
import mediapipe as mp
import numpy as np

# === LAZY LOADING: Variabili globali inizializzate a None ===
_segmenter = None
_mp_selfie_segmentation = None

def get_segmenter():
    """
    Singleton pattern: Carica il modello MediaPipe solo alla prima richiesta.
    Questo impedisce che l'importazione del file blocchi l'avvio del server.
    """
    global _segmenter, _mp_selfie_segmentation
    
    if _segmenter is None:
        # Inizializza solo ora che serve davvero
        _mp_selfie_segmentation = mp.solutions.selfie_segmentation
        _segmenter = _mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
    
    return _segmenter

def get_head_y(image):
    """
    Trova la coordinata Y normalizzata della testa usando la segmentazione.
    """
    # Ottieni l'istanza (caricando il modello se necessario)
    segment = get_segmenter()

    # Controllo sicurezza immagine vuota
    if image is None or image.size == 0:
        return 0.0

    # Converte in RGB per MediaPipe
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Esegui segmentazione
    result = segment.process(rgb_image)
    
    # Se non trova nulla, ritorna 0
    if result.segmentation_mask is None:
        return 0.0

    mask = (result.segmentation_mask > 0.5).astype(np.uint8) * 255  # Maschera binaria

    # Rimuovi piccoli artefatti (Noise reduction)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((5, 5), np.uint8))

    # Trova contorni nella maschera
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        # Nessun contorno rilevato
        return 0.0

    # Seleziona il contorno più grande (probabilmente la persona)
    contour = max(contours, key=cv2.contourArea)

    # Trova la testa (punto con y minima)
    head_point = tuple(contour[contour[:, :, 1].argmin()][0])
    image_height = image.shape[0]
    
    if image_height == 0:
        return 0.0

    # Normalizza in [0,1]
    head_y_normalized = head_point[1] / float(image_height)
    
    return head_y_normalized