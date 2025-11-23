import mediapipe as mp
import numpy as np
from contour import get_head_y

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
        self.hip_velocities = []
        self.contact_start_frame = None
        self.contact_end_frame = None
        self.eccentric_start_frame = None
        self.concentric_start_frame = None
        self.contact_time = 0.0
        self.eccentric_time = 0.0
        self.concentric_time = 0.0

    def calibrate_with_person_height(self, person_height_cm, pose_landmarks, frame_height, frame=None):
        """
        Calibra usando l'altezza reale della persona.
        Accesso a mp_pose locale per evitare caricamenti globali.
        """
        # Accesso locale alle costanti MediaPipe
        mp_pose_landmarks = mp.solutions.pose.PoseLandmark
        
        try:
            left_ankle = pose_landmarks.landmark[mp_pose_landmarks.LEFT_HEEL]
            right_ankle = pose_landmarks.landmark[mp_pose_landmarks.RIGHT_HEEL]

            # Calcola posizione media talloni (piedi)
            ankle_y = (left_ankle.y + right_ankle.y) / 2

            # Ottieni y testa normalizzata tramite segmentazione
            if frame is None:
                raise ValueError("Frame necessario per calcolare la testa con get_head_y")
            
            head_y_norm = float(get_head_y(frame))
            
            # Se get_head_y fallisce (ritorna 0.0), abortire
            if head_y_norm == 0.0:
                return False

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
        self.calibration_frames.append(hip_y)
        if len(self.calibration_frames) >= 30:
            self.baseline_hip_y = np.mean(self.calibration_frames)
            return True
        return False

    def detect_jump_start(self, current_hip_y, threshold=0.05):
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
        if self.baseline_hip_y is None or not self.jump_started:
            return
        height_pixels = self.baseline_hip_y - current_hip_y
        if height_pixels > self.max_jump_height_pixels:
            self.max_jump_height_pixels = height_pixels
            self.jump_max_height_frame = self.current_frame
            if self.pixel_to_cm_ratio:
                self.max_jump_height_cm = height_pixels * self.pixel_to_cm_ratio

    def get_flight_time(self):
        if self.takeoff_frame is not None and self.landing_frame is not None:
            frames_in_air = self.landing_frame - self.takeoff_frame
            return frames_in_air / self.fps
        return 0

    def get_fall_time(self):
        if self.jump_max_height_frame is not None and self.landing_frame is not None:
            frames_falling = self.landing_frame - self.jump_max_height_frame
            return frames_falling / self.fps
        return 0

    def calculate_velocity(self, current_hip_y):
        if len(self.hip_positions) < 2 or not self.pixel_to_cm_ratio:
            return 0.0
        delta_y_pixels = self.hip_positions[-1] - current_hip_y
        delta_t = 1.0 / self.fps
        delta_y_cm = delta_y_pixels * self.pixel_to_cm_ratio
        return delta_y_cm / delta_t

    def detect_contact_phases(self, current_hip_y, velocity):
        if not self.jump_started or self.jump_ended:
            return
        if (self.contact_start_frame is None and 
            current_hip_y > self.baseline_hip_y and 
            self.current_frame > self.takeoff_frame + 10):
            self.contact_start_frame = self.current_frame
        if (self.contact_start_frame is not None and 
            self.contact_end_frame is None and 
            current_hip_y < self.baseline_hip_y):
            self.contact_end_frame = self.current_frame
        if (self.contact_start_frame is not None and 
            self.eccentric_start_frame is None and 
            velocity < -5.0):
            self.eccentric_start_frame = self.current_frame
        if (self.eccentric_start_frame is not None and 
            self.concentric_start_frame is None and 
            velocity > 5.0):
            self.concentric_start_frame = self.current_frame

    def get_contact_time(self):
        if self.contact_start_frame is not None and self.contact_end_frame is not None:
            return (self.contact_end_frame - self.contact_start_frame) / self.fps
        return 0.0

    def get_eccentric_time(self):
        if self.eccentric_start_frame is not None and self.concentric_start_frame is not None:
            return (self.concentric_start_frame - self.eccentric_start_frame) / self.fps
        return 0.0

    def get_concentric_time(self):
        if self.concentric_start_frame is not None and self.contact_end_frame is not None:
            return (self.contact_end_frame - self.concentric_start_frame) / self.fps
        return 0.0

    def get_takeoff_velocity(self):
        if not self.jump_started or not self.hip_velocities:
            return 0.0
        max_velocity = 0.0
        for velocity in self.hip_velocities:
            if velocity > max_velocity:
                max_velocity = velocity
        return max_velocity

    def get_estimated_power(self, body_mass_kg=70.0):
        if not self.jump_started:
            return 0.0
        v0 = self.get_takeoff_velocity()
        max_height = self.max_jump_height_cm / 100.0
        if v0 <= 0 or max_height <= 0:
            return 0.0
        contact_time = self.get_contact_time()
        if contact_time <= 0:
            return 0.0
        kinetic_energy = 0.5 * body_mass_kg * (v0 / 100.0) ** 2
        potential_energy = body_mass_kg * self.g * max_height
        total_energy = kinetic_energy + potential_energy
        return total_energy / contact_time

    def get_average_force(self, body_mass_kg=70.0):
        if not self.jump_started:
            return 0.0
        contact_time = self.get_contact_time()
        if contact_time <= 0:
            return 0.0
        v0 = self.get_takeoff_velocity()
        if v0 <= 0:
            return 0.0
        v0_ms = v0 / 100.0
        return (body_mass_kg * v0_ms) / contact_time

    def process_frame(self, hip_y):
        self.current_frame += 1
        self.hip_positions.append(hip_y)
        
        if self.baseline_hip_y is None and self.calibrated_with_height:
            calibrated = self.calibrate_baseline(hip_y)
            if calibrated:
                return "pronto", None
            return "calibrazione_baseline", None

        if not self.calibrated_with_height:
            return "attesa_calibrazione", None

        self.detect_jump_start(hip_y)
        self.detect_jump_end(hip_y)

        velocity = self.calculate_velocity(hip_y)
        self.hip_velocities.append(velocity)
        self.detect_contact_phases(hip_y, velocity)
        self.update_jump_height(hip_y)

        current_height_pixels = self.baseline_hip_y - hip_y if self.baseline_hip_y else 0
        current_height_cm = current_height_pixels * self.pixel_to_cm_ratio if self.pixel_to_cm_ratio else 0

        return "analisi", current_height_cm

    def reset_keep_calibration(self):
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
        self.hip_velocities = []
        self.contact_start_frame = None
        self.contact_end_frame = None
        self.eccentric_start_frame = None
        self.concentric_start_frame = None
        self.contact_time = 0.0
        self.eccentric_time = 0.0
        self.concentric_time = 0.0