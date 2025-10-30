import cv2
import mediapipe as mp
import numpy as np

# Inizializza MediaPipe SelfieSegmentation
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segment = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)


# # === Percorso immagine ===
# image_path = "C:/Users/bradi/Downloads/jump1_photo.png"  # Cambia con il tuo file

# # Carica immagine
# image = cv2.imread(image_path)
# if image is None:
#     raise FileNotFoundError(f"Impossibile trovare: {image_path}")

# # Converte in RGB per MediaPipe
# rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# # Esegui segmentazione
# result = segment.process(rgb_image)
# mask = (result.segmentation_mask > 0.5).astype(np.uint8) * 255  # Maschera binaria

# # Rimuovi piccoli artefatti
# mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
# mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((5, 5), np.uint8))

# # Trova contorni nella maschera
# contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# if not contours:
#     raise ValueError("Nessun contorno rilevato.")

# # Seleziona il contorno più grande (probabilmente la persona)
# contour = max(contours, key=cv2.contourArea)

# # Trova testa e piedi
# y_min = tuple(contour[contour[:, :, 1].argmin()][0])
# y_max = tuple(contour[contour[:, :, 1].argmax()][0])

# # Disegna contorno e linea testa-piedi
# output = image.copy()
# cv2.drawContours(output, [contour], -1, (0, 255, 0), 2)
# cv2.line(output, y_min, y_max, (0, 0, 255), 2)
# cv2.circle(output, y_min, 5, (255, 0, 0), -1)
# cv2.circle(output, y_max, 5, (0, 255, 255), -1)

# # Salva coordinate su file
# with open("coordinate_persona.txt", "w") as f:
#     f.write(f"Testa: {y_min}\nPiedi: {y_max}\n")

# # Mostra risultati
# cv2.imshow("Maschera", mask)
# cv2.imshow("Contorno Persona", output)
# cv2.waitKey(0)
# cv2.destroyAllWindows()

# def get_head_y1(frame):
#     mp_selfie_segmentation = mp.solutions.selfie_segmentation
#     segment = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
#     result = segment.process(rgb_image)
#     mask = (result.segmentation_mask > 0.5).astype(np.uint8) * 255  # Maschera binaria
#     # Trova contorni nella maschera
#     contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

#     if not contours:
#         raise ValueError("Nessun contorno rilevato.")

#     contour = max(contours, key=cv2.contourArea)
#     y_max = tuple(contour[contour[:, :, 1].argmax()][0])


def get_head_y(image):
    # Converte in RGB per MediaPipe
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Esegui segmentazione
    result = segment.process(rgb_image)
    mask = (result.segmentation_mask > 0.5).astype(np.uint8) * 255  # Maschera binaria

    # Rimuovi piccoli artefatti
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((5, 5), np.uint8))

    # Trova contorni nella maschera
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        raise ValueError("Nessun contorno rilevato.")

    # Seleziona il contorno più grande (probabilmente la persona)
    contour = max(contours, key=cv2.contourArea)

    # Trova la testa (punto con y minima) e normalizza in [0,1]
    head_point = tuple(contour[contour[:, :, 1].argmin()][0])
    image_height = image.shape[0]
    head_y_normalized = head_point[1] / float(image_height)
    print(f"head_y: {head_point[1]}")
    print(f"head_point: {head_point}")
    print(f"image_height: {image_height}")
    return head_y_normalized