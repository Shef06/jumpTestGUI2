"""
Flask Backend Ottimizzato per Jump Analyzer Pro
Miglioramenti: caching, gestione errori, performance
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import time
import os
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import json
from functools import lru_cache
from contour import get_head_y
from jump_analyzer import JumpAnalyzer

app = Flask(__name__)
CORS(app)

# Configurazione
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# Inizializzazione Mediapipe (singleton)
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Stato applicazione con lock per thread safety
state_lock = threading.RLock()
app_state = {
    'video_path': None,
    'is_recording': False,
    'is_analyzing': False,
    'is_calibrating': False,
    'is_paused': False,
    'current_frame': 0,
    'total_frames': 0,
    'cap': None,
    'analyzer': None,
    'video_writer': None,
    'person_height_cm': 174.0,
    'body_mass_kg': 62.0,
    'fps': 30,
    'camera_index': 0,
    'current_video_frame': None,
    'realtime_data': {},
    'trajectory_data': [],
    'velocity_data': [],
    'analysis_thread': None,
    'last_frame_time': 0,  # Cache timing
    'frame_cache': None,   # Frame caching
}

# Costanti per ottimizzazione
FRAME_CACHE_DURATION = 0.033  # ~30fps max update rate
MIN_POLL_INTERVAL = 0.1  # Minimum time between status checks


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_release(obj):
    """Safely release OpenCV objects"""
    try:
        if obj is not None:
            obj.release()
    except Exception as e:
        print(f"Error releasing object: {e}")


def get_state(key=None):
    """Thread-safe state getter"""
    with state_lock:
        if key:
            return app_state.get(key)
        return app_state.copy()


def set_state(**kwargs):
    """Thread-safe state setter"""
    with state_lock:
        app_state.update(kwargs)


@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """Ottiene lista webcam disponibili (cached)"""
    cameras = []
    for i in range(5):  # Ridotto da 10 a 5 per velocità
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(i)
            cap.release()
        else:
            break  # Stop at first unavailable
    return jsonify({'cameras': cameras if cameras else [0]})


@app.route('/api/settings/camera', methods=['POST'])
def set_camera():
    """Imposta camera index"""
    data = request.json
    try:
        set_state(camera_index=int(data.get('index', 0)))
    except Exception:
        set_state(camera_index=0)
    return jsonify({'success': True})


@app.route('/api/settings/fps', methods=['POST'])
def set_fps():
    """Imposta FPS con validazione"""
    data = request.json
    try:
        fps = int(data.get('fps', 30))
        if 1 <= fps <= 240:
            set_state(fps=fps)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'FPS deve essere tra 1 e 240'})
    except:
        return jsonify({'success': False, 'error': 'Valore FPS non valido'})


@app.route('/api/settings/height', methods=['POST'])
def set_height():
    """Imposta altezza persona"""
    data = request.json
    try:
        height = float(data.get('height'))
        if 100 <= height <= 250:
            set_state(person_height_cm=height)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Altezza deve essere tra 100 e 250 cm'})
    except:
        return jsonify({'success': False, 'error': 'Valore non valido'})


@app.route('/api/settings/mass', methods=['POST'])
def set_mass():
    """Imposta massa corporea"""
    data = request.json
    try:
        mass = float(data.get('mass'))
        if 40 <= mass <= 150:
            set_state(body_mass_kg=mass)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Massa deve essere tra 40 e 150 kg'})
    except:
        return jsonify({'success': False, 'error': 'Valore non valido'})


@app.route('/api/video/upload', methods=['POST'])
def upload_video():
    """Upload video file con validazione migliorata"""
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'Nessun file caricato'})
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nessun file selezionato'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(filepath)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Errore salvataggio: {str(e)}'})
        
        # Verifica video
        test_cap = cv2.VideoCapture(filepath)
        if test_cap.isOpened():
            fps = test_cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            test_cap.release()
            
            set_state(video_path=filepath,
                      current_video_frame=None,
                      frame_cache=None,
                      last_frame_time=0)
            
            return jsonify({
                'success': True,
                'video_path': filename,
                'fps': fps,
                'total_frames': total_frames
            })
        else:
            test_cap.release()
            try:
                os.remove(filepath)
            except:
                pass
            return jsonify({'success': False, 'error': 'File video non valido'})
    
    return jsonify({'success': False, 'error': 'Formato file non supportato'})


@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    """Avvia registrazione webcam"""
    if get_state('is_recording'):
        return stop_recording()
    
    camera_index = get_state('camera_index')
    # Prefer DirectShow on Windows for faster device init and lower latency
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    except Exception:
        cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        return jsonify({'success': False, 'error': f'Impossibile aprire camera {camera_index}'})
    
    # Try to reduce internal buffering if supported
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Warm-up: read and discard a few frames to let exposure/white balance settle
    try:
        for _ in range(5):
            cap.read()
    except Exception:
        pass
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"recording_{timestamp}.mp4"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = get_state('fps')
    video_writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
    
    set_state(
        video_path=filepath,
        cap=cap,
        video_writer=video_writer,
        is_recording=True,
        record_start_time=time.time(),
        current_video_frame=None,
        frame_cache=None,
        last_frame_time=0
    )
    
    # Avvia thread registrazione
    thread = threading.Thread(target=recording_loop, daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Registrazione avviata'})


def recording_loop():
    """Loop registrazione con gestione errori migliorata"""
    last_update = 0
    update_interval = 0.033  # ~30fps per UI update
    
    while get_state('is_recording'):
        cap = get_state('cap')
        writer = get_state('video_writer')
        
        if not cap or not cap.isOpened() or not writer:
            break
        
        ret, frame = cap.read()
        if not ret:
            break
        
        elapsed = time.time() - get_state('record_start_time')
        # cv2.putText(frame, f"REC {elapsed:.1f}s", (10, 40),
        #             cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        # cv2.circle(frame, (frame.shape[1] - 40, 40), 15, (0, 0, 255), -1)
        
        writer.write(frame)
        
        # Update frame for streaming (rate limited)
        current_time = time.time()
        if current_time - last_update >= update_interval:
            try:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
                last_update = current_time
            except Exception as e:
                print(f"Error encoding frame: {e}")
        
        time.sleep(0.001)  # Minimal sleep to prevent CPU hogging


@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    """Ferma registrazione con cleanup"""
    set_state(is_recording=False)
    
    time.sleep(0.1)  # Allow recording thread to finish
    
    cap = get_state('cap')
    writer = get_state('video_writer')
    
    safe_release(cap)
    safe_release(writer)
    
    set_state(cap=None, video_writer=None)
    
    filename = os.path.basename(get_state('video_path') or '')
    
    return jsonify({
        'success': True,
        'message': 'Registrazione completata',
        'video_path': filename
    })


@app.route('/api/video/frame', methods=['GET'])
def get_video_frame():
    """Ottiene frame corrente (con cache)"""
    current_time = time.time()
    last_time = get_state('last_frame_time')
    
    # Return cached frame if recent
    if current_time - last_time < FRAME_CACHE_DURATION:
        frame = get_state('frame_cache')
        if frame:
            return jsonify({'success': True, 'frame': frame})
    
    frame = get_state('current_video_frame')
    if frame:
        set_state(last_frame_time=current_time, frame_cache=frame)
        return jsonify({'success': True, 'frame': frame})
    
    return jsonify({'success': False})


@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    """Avvia calibrazione"""
    video_path = get_state('video_path')
    if not video_path or not os.path.exists(video_path):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})
    
    fps = get_state('fps')
    analyzer = JumpAnalyzer(fps=fps)
    
    set_state(is_calibrating=True, analyzer=analyzer)
    
    # Avvia thread calibrazione
    thread = threading.Thread(target=calibration_loop, daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Calibrazione avviata'})


def calibration_loop():
    """Loop calibrazione ottimizzato"""
    video_path = get_state('video_path')
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        set_state(is_calibrating=False)
        return
    
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = get_state('fps')
    max_frames = int(fps * 5)
    
    calibration_success = False
    frames_checked = 0
    last_update = 0
    
    with mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as pose:
        
        while cap.isOpened() and get_state('is_calibrating') and frames_checked < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            frames_checked += 1
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                analyzer = get_state('analyzer')
                person_height = get_state('person_height_cm')
                
                success = analyzer.calibrate_with_person_height(
                    person_height, results.pose_landmarks, frame_height, frame=image
                )
                
                if success:
                    cv2.putText(image, "CALIBRAZIONE COMPLETATA!", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    calibration_success = True
                else:
                    cv2.putText(image, "Cerco persona in posizione eretta...", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            else:
                cv2.putText(image, "Rilevo corpo...", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            
            cv2.putText(image, f"Frame: {frames_checked}/{max_frames}", 
                        (10, frame_height - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Update frame (rate limited)
            current_time = time.time()
            if current_time - last_update >= FRAME_CACHE_DURATION:
                try:
                    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
                    last_update = current_time
                except Exception as e:
                    print(f"Error encoding frame: {e}")
            
            if calibration_success:
                time.sleep(1)
                break
    
    cap.release()
    
    analyzer = get_state('analyzer')
    set_state(
        is_calibrating=False,
        calibration_result={
            'success': calibration_success,
            'ratio': analyzer.pixel_to_cm_ratio if calibration_success else None,
            'height': get_state('person_height_cm') if calibration_success else None
        }
    )


@app.route('/api/calibration/status', methods=['GET'])
def calibration_status():
    """Stato calibrazione"""
    result = get_state('calibration_result')
    if result:
        set_state(calibration_result=None)
        return jsonify(result)
    
    return jsonify({
        'success': get_state('is_calibrating'),
        'in_progress': get_state('is_calibrating')
    })


@app.route('/api/analysis/start', methods=['POST'])
def start_analysis():
    """Avvia analisi"""
    video_path = get_state('video_path')
    if not video_path or not os.path.exists(video_path):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})
    
    analyzer = get_state('analyzer')
    if not analyzer or not analyzer.calibrated_with_height:
        return jsonify({'success': False, 'error': 'Sistema non calibrato'})
    
    set_state(
        is_analyzing=True,
        trajectory_data=[],
        velocity_data=[],
        realtime_data={}
    )
    
    # Avvia thread analisi
    thread = threading.Thread(target=analysis_loop, daemon=True)
    set_state(analysis_thread=thread)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Analisi avviata'})


def analysis_loop():
    """Loop analisi ottimizzato"""
    video_path = get_state('video_path')
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        set_state(is_analyzing=False)
        return
    
    set_state(cap=cap)
    
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    set_state(total_frames=total_frames, current_frame=0)
    
    last_update = 0
    
    with mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as pose:
        
        while cap.isOpened() and get_state('is_analyzing'):
            if get_state('is_paused'):
                time.sleep(0.1)
                continue
            
            ret, frame = cap.read()
            if not ret:
                break
            
            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            set_state(current_frame=current_frame)
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                left_hip = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP]
                right_hip = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_HIP]
                hip_y = ((left_hip.y + right_hip.y) / 2) * frame_height
                
                analyzer = get_state('analyzer')
                status, current_height = analyzer.process_frame(hip_y)
                
                if status == "calibrazione_baseline":
                    cv2.putText(image, "CALIBRAZIONE BASELINE", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                elif status == "analisi":
                    if analyzer.jump_started:
                        cv2.putText(image, "SALTO IN CORSO!", (10, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    else:
                        cv2.putText(image, "FASE PREPARATORIA", (10, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 215, 0), 3)

                    cv2.putText(image, f"Altezza: {current_height:.1f} cm", (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    # Update data (con sampling per ridurre carico)
                    t_seconds = analyzer.current_frame / max(1, analyzer.fps)
                    
                    traj_data = get_state('trajectory_data')
                    traj_data.append({'t': round(t_seconds, 3), 'y': round(current_height, 2)})
                    set_state(trajectory_data=traj_data)
                    
                    if len(analyzer.hip_velocities) > 0:
                        vel_data = get_state('velocity_data')
                        vel_data.append({
                            't': round(t_seconds, 3),
                            'v': round(analyzer.hip_velocities[-1], 2)
                        })
                        set_state(velocity_data=vel_data)
                    
                    body_mass = get_state('body_mass_kg')
                    set_state(realtime_data={
                        'current_height': round(current_height, 1),
                        'max_height': round(analyzer.max_jump_height_cm, 1),
                        'takeoff_velocity': round(analyzer.get_takeoff_velocity(), 1),
                        'estimated_power': round(analyzer.get_estimated_power(body_mass), 1)
                    })
            
            # Update frame (rate limited)
            current_time = time.time()
            if current_time - last_update >= FRAME_CACHE_DURATION:
                try:
                    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
                    last_update = current_time
                except Exception as e:
                    print(f"Error encoding frame: {e}")
            
            # Stop recording when jump ends
            if get_state('is_recording'):
                analyzer = get_state('analyzer')
                if analyzer and analyzer.jump_ended:
                    try:
                        stop_recording()
                    except:
                        set_state(is_recording=False)
    
    cap.release()
    set_state(cap=None, is_analyzing=False)
    
    # Prepara risultati finali
    analyzer = get_state('analyzer')
    body_mass = get_state('body_mass_kg')
    
    set_state(final_results={
        'max_height': round(analyzer.max_jump_height_cm, 2),
        'flight_time': round(analyzer.get_flight_time(), 3),
        'fall_time': round(analyzer.get_fall_time(), 3),
        'contact_time': round(analyzer.get_contact_time(), 3),
        'eccentric_time': round(analyzer.get_eccentric_time(), 3),
        'concentric_time': round(analyzer.get_concentric_time(), 3),
        'takeoff_velocity': round(analyzer.get_takeoff_velocity(), 2),
        'estimated_power': round(analyzer.get_estimated_power(body_mass), 1),
        'average_force': round(analyzer.get_average_force(body_mass), 1),
        'jump_detected': analyzer.jump_started,
        'body_mass_kg': body_mass
    })


@app.route('/api/analysis/status', methods=['GET'])
def analysis_status():
    """Stato analisi"""
    return jsonify({
        'is_analyzing': get_state('is_analyzing'),
        'is_paused': get_state('is_paused'),
        'current_frame': get_state('current_frame'),
        'total_frames': get_state('total_frames')
    })


@app.route('/api/analysis/data', methods=['GET'])
def analysis_data():
    """Dati real-time analisi"""
    return jsonify({
        'realtime': get_state('realtime_data'),
        'trajectory': get_state('trajectory_data'),
        'velocity': get_state('velocity_data')
    })


# Funzioni di calcolo per i risultati
G = 9.81  # Accelerazione di gravità in m/s²

def compute_derived_velocity(trajectory_data):
    """Calcola la velocità derivata dalla traiettoria"""
    if not trajectory_data or len(trajectory_data) < 2:
        return []
    
    velocities = []
    for i in range(1, len(trajectory_data)):
        prev = trajectory_data[i - 1]
        curr = trajectory_data[i]
        delta_t = curr['t'] - prev['t']
        
        if delta_t <= 0 or not np.isfinite(delta_t):
            continue
        
        delta_y = curr['y'] - prev['y']
        velocities.append({
            't': curr['t'],
            'v': delta_y / delta_t
        })
    
    if len(velocities) == 0:
        return []
    
    # Aggiungi un punto iniziale a t=0 (primo tempo disponibile) con v=0
    return [{'t': trajectory_data[0]['t'], 'v': 0}] + velocities


def get_phase_times(trajectory_data, velocity_data):
    """Calcola i tempi delle fasi del salto"""
    if not trajectory_data or len(trajectory_data) < 2 or not velocity_data or len(velocity_data) < 2:
        return None
    
    baseline_height = trajectory_data[0].get('y', 0) if trajectory_data else 0
    contact_start_time = None
    eccentric_start_time = None
    eccentric_end_time = None
    concentric_start_time = None
    concentric_end_time = None
    takeoff_time = None
    
    # Trova inizio contatto / inizio fase eccentrica
    for i, vel_point in enumerate(velocity_data):
        if vel_point['v'] < 0 and contact_start_time is None:
            # Trova l'altezza corrispondente
            height_at_time = next((t for t in trajectory_data if abs(t['t'] - vel_point['t']) < 0.01), None)
            if height_at_time and height_at_time['y'] < baseline_height:
                contact_start_time = vel_point['t']
                eccentric_start_time = vel_point['t']
                break
            elif height_at_time is None:
                contact_start_time = vel_point['t']
                eccentric_start_time = vel_point['t']
                break
    
    # Trova fine fase eccentrica (minimo velocità)
    min_velocity = float('inf')
    min_velocity_index = -1
    for i, vel_point in enumerate(velocity_data):
        if vel_point['v'] < min_velocity:
            min_velocity = vel_point['v']
            min_velocity_index = i
    
    if min_velocity_index >= 0:
        eccentric_end_time = velocity_data[min_velocity_index]['t']
        concentric_start_time = velocity_data[min_velocity_index]['t']
    
    # Trova fine fase concentrica / decollo
    min_height = float('inf')
    min_height_index = -1
    for i, traj_point in enumerate(trajectory_data):
        if traj_point['y'] < min_height:
            min_height = traj_point['y']
            min_height_index = i
    
    if min_height_index >= 0:
        for i in range(min_height_index + 1, len(trajectory_data)):
            if trajectory_data[i]['y'] >= baseline_height:
                # Trova la velocità corrispondente
                velocity_at_time = next((v for v in velocity_data if abs(v['t'] - trajectory_data[i]['t']) < 0.01), None)
                if velocity_at_time and velocity_at_time['v'] > 0:
                    takeoff_time = trajectory_data[i]['t']
                    concentric_end_time = trajectory_data[i]['t']
                    break
    
    return {
        'contactStart': contact_start_time,
        'contactEnd': takeoff_time,
        'eccentricStart': eccentric_start_time,
        'eccentricEnd': eccentric_end_time,
        'concentricStart': concentric_start_time,
        'concentricEnd': concentric_end_time,
        'takeoff': takeoff_time
    }


def calculate_average_force_from_velocity(velocity_data, trajectory_data, body_mass_kg=70.0):
    """Calcola la forza media dalla velocità"""
    if not velocity_data or len(velocity_data) < 2 or body_mass_kg <= 0:
        return 0
    
    CONTACT_THRESHOLD = 5.0  # cm
    
    # Crea una mappa per l'altezza
    height_map = {point['t']: point['y'] for point in trajectory_data} if trajectory_data else {}
    
    # Calcola l'accelerazione dalla velocità
    accelerations = []
    for i in range(1, len(velocity_data)):
        prev = velocity_data[i - 1]
        curr = velocity_data[i]
        delta_t = curr['t'] - prev['t']
        
        if delta_t > 0 and np.isfinite(delta_t):
            v1_ms = prev['v'] / 100  # cm/s -> m/s
            v2_ms = curr['v'] / 100
            a_ms2 = (v2_ms - v1_ms) / delta_t
            
            accelerations.append({
                'time': curr['t'],
                'a_ms2': a_ms2,
                'velocity': curr['v']
            })
    
    if len(accelerations) == 0:
        return 0
    
    # Calcola la forza istantanea solo durante la fase di contatto
    forces = []
    for acc in accelerations:
        height = height_map.get(acc['time'])
        is_in_contact = height is not None and abs(height) <= CONTACT_THRESHOLD
        
        if is_in_contact and abs(acc['a_ms2']) > 0.05:
            force = body_mass_kg * (acc['a_ms2'] + G)
            if force > body_mass_kg * G * 0.3 and acc['velocity'] >= 0:
                forces.append(force)
    
    if len(forces) == 0:
        return 0
    
    return sum(forces) / len(forces)


def calculate_takeoff_velocity(trajectory_data, velocity_data):
    """Calcola la velocità di decollo"""
    if not trajectory_data or len(trajectory_data) < 2 or not velocity_data or len(velocity_data) < 2:
        return 0
    
    baseline_height = trajectory_data[0].get('y', 0) if trajectory_data else 0
    takeoff_time = None
    min_height = float('inf')
    min_height_index = -1
    
    # Trova il minimo dell'altezza
    for i, point in enumerate(trajectory_data):
        if point['y'] < min_height:
            min_height = point['y']
            min_height_index = i
    
    # Dopo il fondo piegamento, trova quando l'altezza torna al baseline
    if min_height_index >= 0:
        for i in range(min_height_index + 1, len(trajectory_data)):
            if trajectory_data[i]['y'] >= baseline_height:
                velocity_at_time = next((v for v in velocity_data if abs(v['t'] - trajectory_data[i]['t']) < 0.01), None)
                if velocity_at_time and velocity_at_time['v'] > 0:
                    takeoff_time = trajectory_data[i]['t']
                    break
    
    # Trova l'altezza massima nella fase di volo
    h_max_volo = 0
    if takeoff_time is not None:
        for point in trajectory_data:
            if point['t'] > takeoff_time and point['y'] > h_max_volo:
                h_max_volo = point['y']
    else:
        if min_height_index >= 0:
            for i in range(min_height_index + 1, len(trajectory_data)):
                if trajectory_data[i]['y'] > h_max_volo:
                    h_max_volo = trajectory_data[i]['y']
    
    # Calcola la velocità di decollo usando v = sqrt(2 * g * h)
    if h_max_volo > 0:
        h_max_m = h_max_volo / 100  # cm -> m
        v_decollo_ms = np.sqrt(2 * G * h_max_m)
        return v_decollo_ms * 100  # m/s -> cm/s
    
    # Fallback: usa il valore diretto della velocità al momento del decollo
    if takeoff_time is not None:
        velocity_at_takeoff = next((v for v in velocity_data if abs(v['t'] - takeoff_time) < 0.01), None)
        if velocity_at_takeoff and velocity_at_takeoff['v'] > 0:
            return velocity_at_takeoff['v']
    
    # Ultimo fallback: trova la velocità massima positiva
    max_velocity = 0
    for vel_point in velocity_data:
        if vel_point['v'] > max_velocity:
            max_velocity = vel_point['v']
    
    return max_velocity


def calculate_concentric_time(trajectory_data, velocity_data, body_mass_kg=70.0):
    """Calcola la fase concentrica"""
    if not trajectory_data or len(trajectory_data) < 2 or not velocity_data or len(velocity_data) < 2:
        return 0
    
    baseline_height = trajectory_data[0].get('y', 0) if trajectory_data else 0
    concentric_start_time = None
    concentric_end_time = None
    
    # Trova il minimo della velocità
    min_velocity = float('inf')
    min_velocity_index = -1
    for i, vel_point in enumerate(velocity_data):
        if vel_point['v'] < min_velocity:
            min_velocity = vel_point['v']
            min_velocity_index = i
    
    # Inizio fase concentrica: quando la velocità diventa positiva dopo il minimo
    if min_velocity_index >= 0:
        for i in range(min_velocity_index, len(velocity_data)):
            if velocity_data[i]['v'] > 0 or (i > min_velocity_index and velocity_data[i]['v'] > velocity_data[i - 1]['v'] + 5):
                concentric_start_time = velocity_data[i]['t']
                break
    
    # Fine fase concentrica: quando avviene il decollo
    min_height = float('inf')
    min_height_index = -1
    for i, point in enumerate(trajectory_data):
        if point['y'] < min_height:
            min_height = point['y']
            min_height_index = i
    
    if min_height_index >= 0 and concentric_start_time is not None:
        for i in range(min_height_index + 1, len(trajectory_data)):
            if trajectory_data[i]['y'] >= baseline_height and trajectory_data[i]['t'] >= concentric_start_time:
                velocity_at_time = next((v for v in velocity_data if abs(v['t'] - trajectory_data[i]['t']) < 0.01), None)
                if velocity_at_time and velocity_at_time['v'] > 0:
                    concentric_end_time = trajectory_data[i]['t']
                    break
    
    # Se non abbiamo trovato la fine, usa il momento della velocità massima
    if concentric_start_time is not None and concentric_end_time is None:
        max_velocity = 0
        max_velocity_time = None
        for vel_point in velocity_data:
            if vel_point['t'] >= concentric_start_time and vel_point['v'] > max_velocity:
                max_velocity = vel_point['v']
                max_velocity_time = vel_point['t']
        if max_velocity_time is not None:
            concentric_end_time = max_velocity_time
    
    if concentric_start_time is not None and concentric_end_time is not None and concentric_end_time > concentric_start_time:
        return concentric_end_time - concentric_start_time
    
    return 0


def calculate_eccentric_time(trajectory_data, velocity_data):
    """Calcola la fase eccentrica"""
    if not trajectory_data or len(trajectory_data) < 2 or not velocity_data or len(velocity_data) < 2:
        return 0
    
    baseline_height = trajectory_data[0].get('y', 0) if trajectory_data else 0
    eccentric_start_time = None
    eccentric_end_time = None
    
    # Trova il minimo della velocità
    min_velocity = float('inf')
    min_velocity_index = -1
    for i, vel_point in enumerate(velocity_data):
        if vel_point['v'] < min_velocity:
            min_velocity = vel_point['v']
            min_velocity_index = i
    
    # Inizio fase eccentrica: quando la velocità diventa negativa per la prima volta
    for vel_point in velocity_data:
        if vel_point['v'] < 0 and eccentric_start_time is None:
            height_at_time = next((t for t in trajectory_data if abs(t['t'] - vel_point['t']) < 0.01), None)
            if height_at_time and height_at_time['y'] < baseline_height:
                eccentric_start_time = vel_point['t']
                break
            elif height_at_time is None:
                eccentric_start_time = vel_point['t']
                break
    
    # Fine fase eccentrica: quando la velocità raggiunge il minimo
    if min_velocity_index >= 0:
        eccentric_end_time = velocity_data[min_velocity_index]['t']
    
    if eccentric_start_time is not None and eccentric_end_time is not None and eccentric_end_time > eccentric_start_time:
        return eccentric_end_time - eccentric_start_time
    
    return 0


def calculate_contact_time(trajectory_data, velocity_data):
    """Calcola il tempo di contatto"""
    if not trajectory_data or len(trajectory_data) < 2 or not velocity_data or len(velocity_data) < 2:
        return 0
    
    baseline_height = trajectory_data[0].get('y', 0) if trajectory_data else 0
    contact_start_time = None
    contact_end_time = None
    
    # Inizio contatto: quando la velocità diventa negativa per la prima volta
    for vel_point in velocity_data:
        if vel_point['v'] < 0 and contact_start_time is None:
            height_at_time = next((t for t in trajectory_data if abs(t['t'] - vel_point['t']) < 0.01), None)
            if height_at_time and height_at_time['y'] < baseline_height:
                contact_start_time = vel_point['t']
                break
            elif height_at_time is None:
                contact_start_time = vel_point['t']
                break
    
    # Fine contatto: quando avviene il decollo
    min_height = float('inf')
    min_height_index = -1
    for i, point in enumerate(trajectory_data):
        if point['y'] < min_height:
            min_height = point['y']
            min_height_index = i
    
    if min_height_index >= 0:
        for i in range(min_height_index + 1, len(trajectory_data)):
            if trajectory_data[i]['y'] >= baseline_height:
                velocity_at_time = next((v for v in velocity_data if abs(v['t'] - trajectory_data[i]['t']) < 0.01), None)
                if velocity_at_time and velocity_at_time['v'] > 0:
                    contact_end_time = trajectory_data[i]['t']
                    break
    
    # Se non abbiamo trovato il decollo, usa il momento della velocità massima
    if contact_start_time is not None and contact_end_time is None:
        max_velocity = 0
        max_velocity_time = None
        for vel_point in velocity_data:
            if vel_point['t'] >= contact_start_time and vel_point['v'] > max_velocity:
                max_velocity = vel_point['v']
                max_velocity_time = vel_point['t']
        if max_velocity_time is not None:
            contact_end_time = max_velocity_time
    
    if contact_start_time is not None and contact_end_time is not None and contact_end_time > contact_start_time:
        return contact_end_time - contact_start_time
    
    # Fallback: usa la somma di fase eccentrica + fase concentrica
    eccentric_time = calculate_eccentric_time(trajectory_data, velocity_data)
    concentric_time = calculate_concentric_time(trajectory_data, velocity_data, 70.0)
    if eccentric_time > 0 and concentric_time > 0:
        return eccentric_time + concentric_time
    
    return 0


def calculate_estimated_power(velocity_data, trajectory_data, body_mass_kg=70.0):
    """Calcola la potenza esplosiva"""
    if not velocity_data or len(velocity_data) < 2 or body_mass_kg <= 0:
        return 0
    
    CONTACT_THRESHOLD = 5.0  # cm
    
    # Crea una mappa per l'altezza
    height_map = {point['t']: point['y'] for point in trajectory_data} if trajectory_data else {}
    
    # Calcola l'accelerazione dalla velocità
    accelerations = []
    for i in range(1, len(velocity_data)):
        prev = velocity_data[i - 1]
        curr = velocity_data[i]
        delta_t = curr['t'] - prev['t']
        
        if delta_t > 0 and np.isfinite(delta_t):
            v1_ms = prev['v'] / 100  # cm/s -> m/s
            v2_ms = curr['v'] / 100
            a_ms2 = (v2_ms - v1_ms) / delta_t
            
            accelerations.append({
                'time': curr['t'],
                'a_ms2': a_ms2,
                'velocity': curr['v']
            })
    
    if len(accelerations) == 0:
        return 0
    
    # Calcola la potenza istantanea solo durante la fase concentrica
    powers = []
    for acc in accelerations:
        height = height_map.get(acc['time'])
        is_in_contact = height is not None and abs(height) <= CONTACT_THRESHOLD
        
        if is_in_contact and acc['velocity'] > 0 and abs(acc['a_ms2']) > 0.05:
            force = body_mass_kg * (acc['a_ms2'] + G)
            if force > body_mass_kg * G * 0.3:
                v_ms = acc['velocity'] / 100  # cm/s -> m/s
                power = force * v_ms
                if power > 0:
                    powers.append(power)
    
    if len(powers) == 0:
        return 0
    
    return max(powers)


@app.route('/api/analysis/results', methods=['GET'])
def analysis_results():
    """Risultati finali con tutti i calcoli"""
    final_results = get_state('final_results')
    if not final_results:
        return jsonify({'success': False, 'error': 'Analisi non completata'})
    
    trajectory_data = get_state('trajectory_data') or []
    velocity_data = get_state('velocity_data') or []
    body_mass_kg = get_state('body_mass_kg') or 70.0
    
    # Calcola la velocità derivata dalla traiettoria
    derived_velocity_data = compute_derived_velocity(trajectory_data)
    
    # Calcola tutti i valori aggiuntivi
    calculated_average_force = calculate_average_force_from_velocity(derived_velocity_data, trajectory_data, body_mass_kg)
    calculated_takeoff_velocity = calculate_takeoff_velocity(trajectory_data, derived_velocity_data)
    calculated_concentric_time = calculate_concentric_time(trajectory_data, derived_velocity_data, body_mass_kg)
    calculated_eccentric_time = calculate_eccentric_time(trajectory_data, derived_velocity_data)
    calculated_contact_time = calculate_contact_time(trajectory_data, derived_velocity_data)
    calculated_estimated_power = calculate_estimated_power(derived_velocity_data, trajectory_data, body_mass_kg)
    phase_times = get_phase_times(trajectory_data, derived_velocity_data)
    
    # Aggiungi i valori calcolati ai risultati
    enhanced_results = final_results.copy()
    enhanced_results.update({
        'calculated_average_force': round(calculated_average_force, 1),
        'calculated_takeoff_velocity': round(calculated_takeoff_velocity, 1),
        'calculated_concentric_time': round(calculated_concentric_time, 3),
        'calculated_eccentric_time': round(calculated_eccentric_time, 3),
        'calculated_contact_time': round(calculated_contact_time, 3),
        'calculated_estimated_power': round(calculated_estimated_power, 1),
    })
    
    return jsonify({
        'success': True,
        'results': enhanced_results,
        'trajectory': trajectory_data,
        'velocity': derived_velocity_data,  # Usa la velocità derivata invece di quella originale
        'phase_times': phase_times
    })


@app.route('/api/analysis/pause', methods=['POST'])
def pause_analysis():
    """Pausa analisi"""
    if get_state('is_analyzing'):
        set_state(is_paused=True)
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/analysis/resume', methods=['POST'])
def resume_analysis():
    """Riprendi analisi"""
    if get_state('is_analyzing'):
        set_state(is_paused=False)
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/analysis/stop', methods=['POST'])
def stop_analysis():
    """Ferma analisi"""
    set_state(is_analyzing=False, is_paused=False)
    return jsonify({'success': True})


@app.route('/api/results/save', methods=['POST'])
def save_results():
    """Salva risultati in file JSON con tutti i valori calcolati"""
    try:
        final_results = get_state('final_results')
        if not final_results:
            return jsonify({'success': False, 'error': 'Nessun risultato da salvare'})
        
        trajectory_data = get_state('trajectory_data') or []
        velocity_data = get_state('velocity_data') or []
        body_mass_kg = get_state('body_mass_kg') or 70.0
        
        # Calcola la velocità derivata dalla traiettoria
        derived_velocity_data = compute_derived_velocity(trajectory_data)
        
        # Calcola tutti i valori aggiuntivi (come nell'endpoint /api/analysis/results)
        calculated_average_force = calculate_average_force_from_velocity(derived_velocity_data, trajectory_data, body_mass_kg)
        calculated_takeoff_velocity = calculate_takeoff_velocity(trajectory_data, derived_velocity_data)
        calculated_concentric_time = calculate_concentric_time(trajectory_data, derived_velocity_data, body_mass_kg)
        calculated_eccentric_time = calculate_eccentric_time(trajectory_data, derived_velocity_data)
        calculated_contact_time = calculate_contact_time(trajectory_data, derived_velocity_data)
        calculated_estimated_power = calculate_estimated_power(derived_velocity_data, trajectory_data, body_mass_kg)
        phase_times = get_phase_times(trajectory_data, derived_velocity_data)
        
        # Aggiungi i valori calcolati ai risultati (senza prefisso "calculated_")
        enhanced_results = final_results.copy()
        enhanced_results.update({
            'average_force': round(calculated_average_force, 1),
            'takeoff_velocity': round(calculated_takeoff_velocity, 1),
            'concentric_time': round(calculated_concentric_time, 3),
            'eccentric_time': round(calculated_eccentric_time, 3),
            'contact_time': round(calculated_contact_time, 3),
            'estimated_power': round(calculated_estimated_power, 1),
        })
        
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'results': enhanced_results,  # Usa enhanced_results invece di final_results
            'trajectory': trajectory_data,
            'velocity': derived_velocity_data,  # Usa la velocità derivata invece di quella originale
            'phase_times': phase_times,  # Aggiungi anche i tempi delle fasi
            'settings': {
                'fps': get_state('fps'),
                'person_height_cm': get_state('person_height_cm'),
                'body_mass_kg': body_mass_kg
            }
        }
        
        # Salvataggio nella directory last_jump (comportamento originale)
        save_dir = os.path.expanduser('~\\AppData\\Roaming\\Kin.ai\\last_jump')
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, 'results.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        # Salvataggio aggiuntivo in test_results se test_id è fornito
        test_id = None
        if request.json:
            test_id = request.json.get('test_id')
        
        test_results_path = None
        if test_id:
            test_dir = os.path.expanduser(f'~\\AppData\\Roaming\\Kin.ai\\test_results\\{test_id}')
            os.makedirs(test_dir, exist_ok=True)
            
            test_results_path = os.path.join(test_dir, 'results.json')
            
            # Leggi il file esistente se presente
            existing_data = {}
            if os.path.exists(test_results_path):
                try:
                    with open(test_results_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    print(f"Errore lettura file esistente: {e}")
                    existing_data = {}
            
            # Trova il prossimo numero di salto
            jump_keys = [key for key in existing_data.keys() if key.startswith('jump_')]
            if jump_keys:
                # Estrai i numeri e trova il massimo
                jump_numbers = []
                for key in jump_keys:
                    try:
                        num = int(key.replace('jump_', ''))
                        jump_numbers.append(num)
                    except ValueError:
                        pass
                next_jump_num = max(jump_numbers) + 1 if jump_numbers else 1
            else:
                next_jump_num = 1
            
            # Aggiungi il nuovo salto
            jump_key = f'jump_{next_jump_num}'
            existing_data[jump_key] = save_data
            
            # Salva il file aggiornato
            with open(test_results_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        response = {
            'success': True, 
            'message': 'Risultati salvati con successo',
            'file_path': file_path
        }
        
        if test_results_path:
            response['test_results_path'] = test_results_path
            response['jump_key'] = jump_key if test_id else None
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Errore salvataggio: {str(e)}'})


@app.route('/api/video/info', methods=['GET'])
def video_info():
    """Info video corrente"""
    path = get_state('video_path')
    total = get_state('total_frames')
    fps = get_state('fps')
    return jsonify({
        'success': True,
        'video_path': os.path.basename(path) if path else None,
        'total_frames': total,
        'fps': fps
    })


@app.route('/api/video/frame_at', methods=['GET'])
def video_frame_at():
    """Frame specifico (ottimizzato con cache)"""
    try:
        index = int(request.args.get('index', 0))
    except:
        return jsonify({'success': False, 'error': 'Indice non valido'})
    
    path = get_state('video_path')
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return jsonify({'success': False, 'error': 'Impossibile aprire il video'})
    
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    index = max(0, min(index, total - 1))
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        return jsonify({'success': False, 'error': 'Frame non disponibile'})
    
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    
    return jsonify({
        'success': True,
        'frame': base64.b64encode(buffer).decode('utf-8'),
        'index': index,
        'total_frames': total
    })


if __name__ == '__main__':
    print("🚀 Avvio server Flask su http://127.0.0.1:5000")
    
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)