import mediapipe as mp
import numpy as np
from contour import get_head_y

mp_pose = mp.solutions.pose


class JumpAnalyzer:
    """Classe per analizzare i salti verticali"""

    def __init__(self, fps=30):
        self.fps = fps
        self.g = 9.81
        self.baseline_hip_y = None
        self.max_jump_height_pixels = 0
        self.max_jump_height_cm = 0
        self.jump_started = False
        self.jump_ended = False
        self.jump_max_height_frame = None
        self.jump_fall = None
        self.takeoff_frame = None
        self.landing_frame = None
        self.current_frame = 0
        self.hip_positions = []
        self.calibration_frames = []
        self.pixel_to_cm_ratio = None
        self.calibrated_with_height = False
        self.person_height_cm = None
        
        # Nuove variabili per analisi fasi
        self.hip_velocities = []  # Velocità del baricentro
        self.contact_start_frame = None  # Inizio contatto con il suolo
        self.contact_end_frame = None    # Fine contatto con il suolo
        self.eccentric_start_frame = None # Inizio fase eccentrica
        self.concentric_start_frame = None # Inizio fase concentrica
        self.contact_time = 0.0  # Tempo di contatto in secondi
        self.eccentric_time = 0.0  # Tempo fase eccentrica
        self.concentric_time = 0.0  # Tempo fase concentrica

    def calibrate_with_person_height(self, person_height_cm, pose_landmarks, frame_height, frame=None):
        """
        Calibra usando l'altezza reale della persona
        Calcola quanti pixel occupa la persona nel frame e li confronta con l'altezza reale
        """
        try:
            left_ankle = pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_HEEL]
            right_ankle = pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_HEEL]

            # Calcola posizione media talloni (piedi)
            ankle_y = (left_ankle.y + right_ankle.y) / 2

            # Ottieni y testa normalizzata tramite segmentazione (richiede frame BGR)
            if frame is None:
                raise ValueError("Frame necessario per calcolare la testa con get_head_y")
            head_y_norm = float(get_head_y(frame))

            # Altezza persona in pixel: testa (y minima) -> tallone (y media)
            person_height_pixels = abs((ankle_y - head_y_norm) * frame_height)

            # Verifica che i dati siano validi
            if person_height_pixels < 100:  # Troppo piccolo, probabilmente errore
                return False

            # Calcola il rapporto pixel->cm
            self.pixel_to_cm_ratio = person_height_cm / person_height_pixels
            self.calibrated_with_height = True
            self.person_height_cm = person_height_cm

            return True

        except Exception as e:
            print(f"Errore calibrazione: {e}")
            return False

    def calibrate_baseline(self, hip_y):
        """
        Calibra la posizione baseline del bacino (dopo calibrazione altezza)
        """
        self.calibration_frames.append(hip_y)

        if len(self.calibration_frames) >= 30:
            self.baseline_hip_y = np.mean(self.calibration_frames)
            return True
        return False

    def detect_jump_start(self, current_hip_y, threshold=0.05):
        """Rileva l'inizio del salto"""
        if self.baseline_hip_y is None:
            return False

        movement = self.baseline_hip_y - current_hip_y
        threshold_pixels = threshold * abs(self.baseline_hip_y)

        if movement > threshold_pixels and not self.jump_started:
            self.jump_started = True
            self.takeoff_frame = self.current_frame

            return True
        return False

    def detect_jump_end(self, current_hip_y, threshold=0.03):
        """Rileva la fine del salto"""
        if not self.jump_started or self.jump_ended:
            return False

        distance_from_baseline = abs(current_hip_y - self.baseline_hip_y)
        threshold_pixels = threshold * abs(self.baseline_hip_y)

        if distance_from_baseline < threshold_pixels and self.current_frame > self.takeoff_frame + 5:
            self.jump_ended = True
            self.landing_frame = self.current_frame
            self.jump_fall = (self.landing_frame - self.jump_max_height_frame) / self.fps
            return True
        return False

    def update_jump_height(self, current_hip_y):
        """Aggiorna l'altezza massima raggiunta"""
        if self.baseline_hip_y is None or not self.jump_started:
            return

        height_pixels = self.baseline_hip_y - current_hip_y

        if height_pixels > self.max_jump_height_pixels:
            self.max_jump_height_pixels = height_pixels
            self.jump_max_height_frame = self.current_frame

            if self.pixel_to_cm_ratio:
                self.max_jump_height_cm = height_pixels * self.pixel_to_cm_ratio

    def get_flight_time(self):
        """Calcola il tempo di volo in secondi"""
        if self.takeoff_frame is not None and self.landing_frame is not None:
            frames_in_air = self.landing_frame - self.takeoff_frame
            return frames_in_air / self.fps
        return 0

    def get_fall_time(self):
        """Calcola il tempo di caduta in secondi"""
        if self.jump_max_height_frame is not None and self.landing_frame is not None:
            frames_falling = self.landing_frame - self.jump_max_height_frame
            return frames_falling / self.fps
        return 0

    def calculate_velocity(self, current_hip_y):
        """Calcola la velocità del baricentro in cm/s"""
        if len(self.hip_positions) < 2 or not self.pixel_to_cm_ratio:
            return 0.0
        
        # Calcola differenza di posizione tra frame corrente e precedente
        # Movimento verso l'alto (y diminuisce) è positivo
        delta_y_pixels = self.hip_positions[-1] - current_hip_y
        delta_t = 1.0 / self.fps  # Tempo tra frame
        
        # Converte da pixel a cm
        delta_y_cm = delta_y_pixels * self.pixel_to_cm_ratio
        velocity_cm_s = delta_y_cm / delta_t
        
        return velocity_cm_s

    def detect_contact_phases(self, current_hip_y, velocity):
        """Rileva le fasi di contatto e le transizioni eccentrica-concentrica"""
        if not self.jump_started or self.jump_ended:
            return
        
        # Rileva inizio contatto (quando si scende sotto baseline)
        if (self.contact_start_frame is None and 
            current_hip_y > self.baseline_hip_y and 
            self.current_frame > self.takeoff_frame + 10):  # Dopo il decollo
            self.contact_start_frame = self.current_frame
        
        # Rileva fine contatto (quando si risale sopra baseline)
        if (self.contact_start_frame is not None and 
            self.contact_end_frame is None and 
            current_hip_y < self.baseline_hip_y):
            self.contact_end_frame = self.current_frame
        
        # Rileva inizio fase eccentrica (velocità negativa durante contatto)
        if (self.contact_start_frame is not None and 
            self.eccentric_start_frame is None and 
            velocity < -5.0):  # Soglia velocità negativa
            self.eccentric_start_frame = self.current_frame
        
        # Rileva inizio fase concentrica (velocità positiva dopo eccentrica)
        if (self.eccentric_start_frame is not None and 
            self.concentric_start_frame is None and 
            velocity > 5.0):  # Soglia velocità positiva
            self.concentric_start_frame = self.current_frame

    def get_contact_time(self):
        """Calcola il tempo di contatto in secondi"""
        if self.contact_start_frame is not None and self.contact_end_frame is not None:
            frames_contact = self.contact_end_frame - self.contact_start_frame
            return frames_contact / self.fps
        return 0.0

    def get_eccentric_time(self):
        """Calcola il tempo della fase eccentrica in secondi"""
        if self.eccentric_start_frame is not None and self.concentric_start_frame is not None:
            frames_eccentric = self.concentric_start_frame - self.eccentric_start_frame
            return frames_eccentric / self.fps
        return 0.0

    def get_concentric_time(self):
        """Calcola il tempo della fase concentrica in secondi"""
        if self.concentric_start_frame is not None and self.contact_end_frame is not None:
            frames_concentric = self.contact_end_frame - self.concentric_start_frame
            return frames_concentric / self.fps
        return 0.0

    def get_takeoff_velocity(self):
        """Calcola la velocità di take-off (v0) in cm/s"""
        if not self.jump_started or not self.hip_velocities:
            return 0.0
        
        # Trova la velocità massima positiva (verso l'alto) durante il salto
        max_velocity = 0.0
        for velocity in self.hip_velocities:
            if velocity > max_velocity:
                max_velocity = velocity
        
        return max_velocity

    def get_estimated_power(self, body_mass_kg=70.0):
        """Calcola la potenza stimata in Watt"""
        if not self.jump_started:
            return 0.0
        
        # Usa la velocità di take-off e l'altezza massima
        v0 = self.get_takeoff_velocity()
        max_height = self.max_jump_height_cm / 100.0  # Converti in metri
        
        if v0 <= 0 or max_height <= 0:
            return 0.0
        
        # Potenza = (m * g * h) / t_contact
        # Dove t_contact è il tempo di contatto
        contact_time = self.get_contact_time()
        if contact_time <= 0:
            return 0.0
        
        # Energia cinetica + potenziale
        kinetic_energy = 0.5 * body_mass_kg * (v0 / 100.0) ** 2  # v0 in m/s
        potential_energy = body_mass_kg * self.g * max_height
        
        total_energy = kinetic_energy + potential_energy
        power = total_energy / contact_time
        
        return power

    def get_average_force(self, body_mass_kg=70.0):
        """Calcola la forza media durante il salto in Newton"""
        if not self.jump_started:
            return 0.0
        
        contact_time = self.get_contact_time()
        if contact_time <= 0:
            return 0.0
        
        # Forza media = (m * v0) / t_contact
        v0 = self.get_takeoff_velocity()
        if v0 <= 0:
            return 0.0
        
        # v0 in m/s, massa in kg
        v0_ms = v0 / 100.0
        average_force = (body_mass_kg * v0_ms) / contact_time
        
        return average_force

    def process_frame(self, hip_y):
        """Processa un singolo frame"""
        self.current_frame += 1
        self.hip_positions.append(hip_y)

        # Fase di calibrazione baseline
        if self.baseline_hip_y is None and self.calibrated_with_height:
            calibrated = self.calibrate_baseline(hip_y)
            if calibrated:
                return "pronto", None
            return "calibrazione_baseline", None

        if not self.calibrated_with_height:
            return "attesa_calibrazione", None

        # Rileva inizio e fine salto
        self.detect_jump_start(hip_y)
        self.detect_jump_end(hip_y)

        # Calcola velocità e rileva fasi
        velocity = self.calculate_velocity(hip_y)
        self.hip_velocities.append(velocity)
        self.detect_contact_phases(hip_y, velocity)

        # Aggiorna altezza massima
        self.update_jump_height(hip_y)

        # Calcola altezza corrente
        current_height_pixels = self.baseline_hip_y - hip_y if self.baseline_hip_y else 0
        current_height_cm = current_height_pixels * self.pixel_to_cm_ratio if self.pixel_to_cm_ratio else 0

        return "analisi", current_height_cm

    def reset_keep_calibration(self):
        """Reimposta lo stato del salto mantenendo la calibrazione pixel->cm e l'altezza persona.

        Questo consente di ripetere il test senza dover ricalibrare l'altezza.
        """
        # Mantieni: fps, g, pixel_to_cm_ratio, calibrated_with_height, person_height_cm
        # Reimposta: metriche e stati del salto e baseline
        self.baseline_hip_y = None
        self.max_jump_height_pixels = 0
        self.max_jump_height_cm = 0
        self.jump_started = False
        self.jump_ended = False
        self.jump_max_height_frame = None
        self.jump_fall = None
        self.takeoff_frame = None
        self.landing_frame = None
        self.current_frame = 0
        self.hip_positions = []
        self.calibration_frames = []
        
        # Reset nuove variabili per analisi fasi
        self.hip_velocities = []
        self.contact_start_frame = None
        self.contact_end_frame = None
        self.eccentric_start_frame = None
        self.concentric_start_frame = None
        self.contact_time = 0.0
        self.eccentric_time = 0.0
        self.concentric_time = 0.0