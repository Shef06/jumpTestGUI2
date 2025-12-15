import numpy as np

class JumpAnalyzer:
    """
    Analizzatore di salti basato sulla fisica del tempo di volo (5 Fasi).
    Sostituisce la logica basata sull'altezza utente.
    """

    def __init__(self, fps=30):
        self.fps = fps
        self.g = 9.81
        
        # --- FASE 1: Dati Grezzi ---
        self.raw_hip_y_pixels = []  # Lista posizioni Y in pixel
        self.timestamps = []        # Tempi relativi
        self.baseline_pixel = None  # Posizione 'zero' (in piedi) in pixel
        
        # Stato runtime
        self.current_frame = 0
        self.jump_started = False
        self.jump_ended = False
        
        # Risultati calcolati (Fase 5)
        self.calibrated_with_height = False # Flag mantenuto per compatibilità app.py
        self.normalized_trajectory = [] 
        self.derived_velocity = []
        self.final_stats = None

        # Variabili legacy per compatibilità getter immediati (saranno 0 fino alla fine)
        self.max_jump_height_cm = 0
        self.hip_velocities = [] 

    def calibrate_baseline(self, hip_y_pixel):
        """
        Cattura la posizione in piedi (baseline). 
        Sostituisce la vecchia calibrazione con altezza.
        """
        if self.baseline_pixel is None:
            self.baseline_pixel = hip_y_pixel
        else:
            # Media mobile esponenziale per stabilizzare la baseline
            self.baseline_pixel = (self.baseline_pixel * 0.9) + (hip_y_pixel * 0.1)
        
        # Impostiamo a True per dire ad app.py che siamo pronti
        self.calibrated_with_height = True 
        return True

    def process_frame(self, hip_y_pixel):
        """
        FASE 1: Raccolta dati frame per frame.
        Non esegue calcoli fisici complessi qui, solo raccolta.
        """
        self.current_frame += 1
        t = self.current_frame / self.fps
        
        self.raw_hip_y_pixels.append(hip_y_pixel)
        self.timestamps.append(t)

        # Logica minimale per rilevare lo stato del salto (utile per fermare la registrazione)
        status = "attesa_calibrazione"
        current_height_dummy = 0.0

        if self.baseline_pixel:
            status = "analisi"
            # Nota: in pixel, valori più alti = più in basso nello schermo.
            # Salto = hip_y_pixel diminuisce (va verso l'alto dello schermo)
            diff = self.baseline_pixel - hip_y_pixel
            
            # Soglia empirica (es. 50px) per dire "ha iniziato a saltare"
            if diff > 50 and not self.jump_started: 
                self.jump_started = True
            
            # Rilevamento fine salto (ritorno vicino alla baseline dopo il salto)
            if self.jump_started and not self.jump_ended:
                # Se siamo tornati giù (diff < 20px) e il salto è durato almeno 10 frame
                if diff < 30 and len(self.raw_hip_y_pixels) > (self.current_frame - 10):
                     self.jump_ended = True

        return status, current_height_dummy

    def calculate_metrics_post_flight(self, body_mass_kg=70.0):
        """
        Esegue FASE 2, 3, 4 e 5.
        Deve essere chiamato alla fine dell'acquisizione.
        """
        if not self.raw_hip_y_pixels or not self.baseline_pixel:
            return None

        # Convertiamo in numpy array
        y_pixels = np.array(self.raw_hip_y_pixels)
        baseline = self.baseline_pixel
        
        # Altezza in pixel rispetto alla baseline (Invertiamo asse: Baseline - Y)
        height_curve_px = baseline - y_pixels
        
        # --- FASE 2: Trova Decollo e Atterraggio (Tempo di Volo) ---
        max_px = np.max(height_curve_px)
        if max_px < 10: return None # Nessun salto rilevato
        
        threshold_px = max(10, max_px * 0.15) # Soglia 15% del picco
        in_air_indices = np.where(height_curve_px > threshold_px)[0]
        
        if len(in_air_indices) < 5: return None

        takeoff_idx = in_air_indices[0]
        landing_idx = in_air_indices[-1]
        
        flight_frames = landing_idx - takeoff_idx
        flight_time = flight_frames / self.fps
        
        if flight_time <= 0: return None

        # --- FASE 3: Calcola Altezza Fisica (h = 1/8 * g * t^2) ---
        # Formula cinematica per il salto verticale da fermo basata sul tempo di volo
        max_height_cm_physic = (0.125 * self.g * (flight_time ** 2)) * 100
        self.max_jump_height_cm = max_height_cm_physic # Aggiorna variabile membro
        
        # --- FASE 4: Normalizzazione (Pixel -> CM) ---
        # Troviamo il picco in pixel durante la fase di volo
        peak_px_val = np.max(height_curve_px[takeoff_idx:landing_idx+1])
        
        if peak_px_val == 0: return None
        
        # Calcolo rapporto di conversione
        px_to_cm_ratio = max_height_cm_physic / peak_px_val
        
        # Normalizziamo l'intera traiettoria
        self.normalized_trajectory = []
        y_cm_array = height_curve_px * px_to_cm_ratio # Array numpy per calcoli successivi
        
        for i, val_cm in enumerate(y_cm_array):
            self.normalized_trajectory.append({
                't': round(self.timestamps[i], 3),
                'y': round(val_cm, 2)
            })

        # --- FASE 5: Calcoli Derivati sul Grafico Normalizzato ---
        dt = 1.0 / self.fps
        
        # 1. Velocità (m/s)
        pos_meters = y_cm_array / 100.0
        velocities_ms = np.gradient(pos_meters, dt)
        
        self.derived_velocity = []
        for i, v in enumerate(velocities_ms):
            self.derived_velocity.append({
                't': round(self.timestamps[i], 3),
                'v': round(v * 100, 2) # Salviamo in cm/s per grafico frontend
            })
            
        # 2. Accelerazione (m/s^2)
        accelerations = np.gradient(velocities_ms, dt)
        
        # 3. Forza (N) -> F = m(a + g)
        forces = (accelerations + self.g) * body_mass_kg
        
        # 4. Potenza (W) -> P = F * v
        powers = forces * velocities_ms
        
        # Estrazione metriche puntuali
        takeoff_velocity = velocities_ms[takeoff_idx] if takeoff_idx < len(velocities_ms) else 0
        
        # Potenza Massima (fase spinta)
        push_phase_powers = powers[0:takeoff_idx]
        max_power = np.max(push_phase_powers) if len(push_phase_powers) > 0 else 0
        
        # Forza Media (fase spinta attiva > peso corporeo)
        body_weight = body_mass_kg * self.g
        active_push_indices = np.where((forces[0:takeoff_idx] > body_weight) & (velocities_ms[0:takeoff_idx] > 0))[0]
        
        avg_force = 0
        if len(active_push_indices) > 0:
            avg_force = np.mean(forces[active_push_indices])
            
        # Tempi Fasi 
        # Eccentrica: inizio discesa (v < 0) fino a inversione (v=0)
        # Concentrica: inversione (v=0) fino a stacco
        min_v_idx = np.argmin(velocities_ms[0:takeoff_idx]) if takeoff_idx > 0 else 0
        
        # Trova inizio eccentrica (quando v diventa negativa significativamente)
        ecc_start_idx = 0
        for i in range(min_v_idx):
            if velocities_ms[i] < -0.1: # soglia
                ecc_start_idx = i
                break
        
        eccentric_time = (self.timestamps[min_v_idx] - self.timestamps[ecc_start_idx]) if min_v_idx > ecc_start_idx else 0
        concentric_time = (self.timestamps[takeoff_idx] - self.timestamps[min_v_idx]) if min_v_idx < takeoff_idx else 0
        fall_time = (self.timestamps[landing_idx] - self.timestamps[np.argmax(y_cm_array)])
        
        self.final_stats = {
            'max_height': round(max_height_cm_physic, 2),
            'flight_time': round(flight_time, 3),
            'fall_time': round(fall_time, 3),
            'takeoff_velocity': round(takeoff_velocity, 2), # m/s
            'estimated_power': round(max_power, 1),
            'average_force': round(avg_force, 1),
            'eccentric_time': round(eccentric_time, 3),
            'concentric_time': round(concentric_time, 3),
            'contact_time': round(eccentric_time + concentric_time, 3),
            'jump_detected': True,
            'body_mass_kg': body_mass_kg,
            
            # Chiavi "calculated_" per compatibilità frontend esistente
            'calculated_average_force': round(avg_force, 1),
            'calculated_takeoff_velocity': round(takeoff_velocity, 2),
            'calculated_concentric_time': round(concentric_time, 3),
            'calculated_eccentric_time': round(eccentric_time, 3),
            'calculated_contact_time': round(eccentric_time + concentric_time, 3),
            'calculated_estimated_power': round(max_power, 1),
        }
        
        return self.final_stats

    def reset(self):
        self.raw_hip_y_pixels = []
        self.timestamps = []
        # Non resettiamo baseline_pixel per comodità tra salti
        self.jump_started = False
        self.jump_ended = False
        self.current_frame = 0
        self.normalized_trajectory = []
        self.derived_velocity = []
        self.final_stats = None
        self.max_jump_height_cm = 0