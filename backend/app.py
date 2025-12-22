"""
Flask Backend Ottimizzato per Jump Analyzer Pro
Logica: 5-Fasi (Tempo di Volo) - Senza calibrazione altezza utente
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
# MediaPipe viene caricato lazy solo quando serve (calibration_loop e analysis_loop)
import time
import os
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import json
# Import
from jump_analyzer import JumpAnalyzer

app = Flask(__name__)
CORS(app)

# Configurazione
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

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
    'person_height_cm': 175.0, # Mantenuto per UI, non usato per calcoli
    'body_mass_kg': 75.0,
    'fps': 30,
    'camera_index': 0,
    'current_video_frame': None,
    'realtime_data': {},
    'trajectory_data': [],
    'velocity_data': [],
    'final_results': None, # Cache risultati
    'analysis_thread': None,
    'last_frame_time': 0,
    'frame_cache': None,
}

FRAME_CACHE_DURATION = 0.033

# --- Helper Functions Base ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_release(obj):
    try:
        if obj is not None: obj.release()
    except: pass

def get_state(key=None):
    with state_lock:
        if key: return app_state.get(key)
        return app_state.copy()

def set_state(**kwargs):
    with state_lock:
        app_state.update(kwargs)

# --- ROTTE CONFIGURAZIONE & VIDEO (Invariate o minimamente adattate) ---

@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    cameras = []
    for i in range(2): 
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cameras.append(i)
                cap.release()
        except: pass
    return jsonify({'cameras': cameras if cameras else [0]})

@app.route('/api/settings/camera', methods=['POST'])
def set_camera():
    data = request.json
    set_state(camera_index=int(data.get('index', 0)))
    return jsonify({'success': True})

@app.route('/api/settings/fps', methods=['POST'])
def set_fps():
    data = request.json
    set_state(fps=int(data.get('fps', 30)))
    return jsonify({'success': True})

@app.route('/api/settings/height', methods=['POST'])
def set_height():
    # Salviamo comunque l'altezza se il frontend la manda, ma non la usiamo per i calcoli
    data = request.json
    set_state(person_height_cm=float(data.get('height', 175)))
    return jsonify({'success': True})

@app.route('/api/settings/mass', methods=['POST'])
def set_mass():
    data = request.json
    set_state(body_mass_kg=float(data.get('mass', 75)))
    return jsonify({'success': True})

@app.route('/api/video/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files: return jsonify({'success': False})
    file = request.files['video']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        test_cap = cv2.VideoCapture(filepath)
        fps = test_cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        test_cap.release()
        
        set_state(video_path=filepath, fps=fps, total_frames=total_frames, final_results=None)
        return jsonify({'success': True, 'video_path': filename, 'fps': fps, 'total_frames': total_frames})
    return jsonify({'success': False})

@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    camera_index = get_state('camera_index')
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened(): return jsonify({'success': False})
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"rec_{timestamp}.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(filepath, fourcc, get_state('fps'), (int(cap.get(3)), int(cap.get(4))))
    
    set_state(video_path=filepath, cap=cap, video_writer=writer, is_recording=True)
    threading.Thread(target=recording_loop, daemon=True).start()
    return jsonify({'success': True})

def recording_loop():
    while get_state('is_recording'):
        cap = get_state('cap')
        writer = get_state('video_writer')
        if cap and writer:
            ret, frame = cap.read()
            if ret:
                writer.write(frame)
                _, buffer = cv2.imencode('.jpg', frame)
                set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
            else: break
        time.sleep(0.001)

@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    set_state(is_recording=False)
    time.sleep(0.2)
    safe_release(get_state('cap'))
    safe_release(get_state('video_writer'))
    set_state(cap=None, video_writer=None)
    return jsonify({'success': True, 'video_path': os.path.basename(get_state('video_path'))})

@app.route('/api/video/frame', methods=['GET'])
def get_video_frame():
    frame = get_state('current_video_frame')
    return jsonify({'success': True, 'frame': frame}) if frame else jsonify({'success': False})


# --- NUOVA LOGICA CALIBRAZIONE (SOLO BASELINE) ---

@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    """Avvia la ricerca della baseline (posizione zero in piedi)"""
    video_path = get_state('video_path')
    if not video_path: return jsonify({'success': False})
    
    analyzer = JumpAnalyzer(fps=get_state('fps'))
    set_state(is_calibrating=True, analyzer=analyzer)
    
    threading.Thread(target=calibration_loop, daemon=True).start()
    return jsonify({'success': True, 'message': 'Acquisizione baseline avviata'})

def calibration_loop():
    # Lazy loading: carica MediaPipe solo quando serve
    import mediapipe as mp
    
    video_path = get_state('video_path')
    cap = cv2.VideoCapture(video_path)
    mp_pose = mp.solutions.pose
    
    max_frames = int(get_state('fps') * 2) # 2 secondi di calibrazione
    count = 0
    
    with mp_pose.Pose(min_detection_confidence=0.5, model_complexity=1) as pose:
        while cap.isOpened() and get_state('is_calibrating') and count < max_frames:
            ret, frame = cap.read()
            if not ret: break
            
            # Analisi Pose
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.pose_landmarks:
                # Estrai Y bacino
                landmarks = results.pose_landmarks.landmark
                hip_y = ((landmarks[mp_pose.PoseLandmark.LEFT_HIP].y + 
                          landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y) / 2) * frame.shape[0]
                
                # Salva baseline
                get_state('analyzer').calibrate_baseline(hip_y)
                
                cv2.putText(frame, "ACQUISIZIONE BASELINE...", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            
            _, buffer = cv2.imencode('.jpg', frame)
            set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
            count += 1
            time.sleep(0.01)

    cap.release()
    set_state(is_calibrating=False, calibration_result={'success': True, 'message': 'Baseline OK'})

@app.route('/api/calibration/status', methods=['GET'])
def calibration_status():
    res = get_state('calibration_result')
    if res:
        set_state(calibration_result=None)
        return jsonify(res)
    return jsonify({'success': get_state('is_calibrating')})


# --- NUOVA LOGICA ANALISI (5 FASI) ---

@app.route('/api/analysis/start', methods=['POST'])
def start_analysis():
    video_path = get_state('video_path')
    if not video_path: return jsonify({'success': False})
    
    analyzer = get_state('analyzer')
    if not analyzer:
        analyzer = JumpAnalyzer(fps=get_state('fps'))
        set_state(analyzer=analyzer)
    
    # Reset FASE 1
    analyzer.reset()
    
    set_state(is_analyzing=True, trajectory_data=[], velocity_data=[], realtime_data={}, final_results=None)
    threading.Thread(target=analysis_loop, daemon=True).start()
    return jsonify({'success': True})

def analysis_loop():
    """FASE 1: Raccolta Dati Raw"""
    # Lazy loading: carica MediaPipe solo quando serve
    import mediapipe as mp
    
    cap = cv2.VideoCapture(get_state('video_path'))
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    analyzer = get_state('analyzer')
    
    with mp_pose.Pose(min_detection_confidence=0.5, model_complexity=1) as pose:
        while cap.isOpened() and get_state('is_analyzing'):
            if get_state('is_paused'): 
                time.sleep(0.1)
                continue
                
            ret, frame = cap.read()
            if not ret: break
            
            set_state(current_frame=int(cap.get(cv2.CAP_PROP_POS_FRAMES)))
            
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                
                # Prendi Y bacino e passala all'analyzer
                landmarks = results.pose_landmarks.landmark
                hip_y = ((landmarks[mp_pose.PoseLandmark.LEFT_HIP].y + 
                          landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y) / 2) * frame.shape[0]
                
                # Se non calibrato, fallo al volo
                if analyzer.baseline_pixel is None:
                    analyzer.calibrate_baseline(hip_y)
                
                status, _ = analyzer.process_frame(hip_y)
                
                color = (0, 0, 255) if analyzer.jump_started else (0, 255, 0)
                msg = "SALTO RILEVATO" if analyzer.jump_started else "PRONTO"
                cv2.putText(frame, msg, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            # Update frame visuale
            _, buffer = cv2.imencode('.jpg', frame)
            set_state(current_video_frame=base64.b64encode(buffer).decode('utf-8'))
            
            # Stop automatico registrazione
            if get_state('is_recording') and analyzer.jump_ended:
                time.sleep(0.5) # Buffer finale
                # La stop viene gestita dal frontend o dalla rotta stop manuale
                
    cap.release()
    set_state(is_analyzing=False)

@app.route('/api/analysis/results', methods=['GET'])
def analysis_results():
    """
    FASE 2, 3, 4, 5: Calcolo Post-Hoc
    Qui vengono generati i dati fisici reali.
    """
    analyzer = get_state('analyzer')
    if not analyzer: return jsonify({'success': False})
    
    # Se già calcolati, ritorna cache
    if get_state('final_results'):
        return jsonify({
            'success': True,
            'results': get_state('final_results'),
            'trajectory': get_state('trajectory_data'),
            'velocity': get_state('velocity_data'),
            'phase_times': {} # Opzionale
        })

    # Calcola ora
    body_mass = get_state('body_mass_kg')
    stats = analyzer.calculate_metrics_post_flight(body_mass_kg=body_mass)
    
    if stats is None:
        return jsonify({'success': False, 'error': 'Dati insufficienti per calcolo tempo di volo'})
    
    # Salva in stato globale
    set_state(
        final_results=stats,
        trajectory_data=analyzer.normalized_trajectory,
        velocity_data=analyzer.derived_velocity
    )
    
    return jsonify({
        'success': True,
        'results': stats,
        'trajectory': analyzer.normalized_trajectory,
        'velocity': analyzer.derived_velocity,
        'phase_times': {
            'takeoff': stats.get('flight_time', 0), # Placeholder
            'eccentric': stats.get('eccentric_time', 0),
            'concentric': stats.get('concentric_time', 0)
        }
    })

# --- ROTTE UTILITY (Stop, Pause, Save) ---

@app.route('/api/analysis/stop', methods=['POST'])
def stop_analysis():
    set_state(is_analyzing=False, is_paused=False)
    return jsonify({'success': True})

@app.route('/api/analysis/pause', methods=['POST'])
def pause_analysis():
    set_state(is_paused=True)
    return jsonify({'success': True})

@app.route('/api/analysis/resume', methods=['POST'])
def resume_analysis():
    set_state(is_paused=False)
    return jsonify({'success': True})

@app.route('/api/analysis/status', methods=['GET'])
def analysis_status():
    return jsonify({
        'is_analyzing': get_state('is_analyzing'),
        'current_frame': get_state('current_frame'),
        'total_frames': get_state('total_frames')
    })

@app.route('/api/results/save', methods=['POST'])
def save_results():
    # Ottieni testId e dati opzionali dal body della richiesta
    data_request = request.json or {}
    test_id = data_request.get('testId')
    if not test_id:
        return jsonify({'success': False, 'error': 'testId richiesto'})
    
    # Se i dati sono forniti nel body, usali; altrimenti usa final_results dallo stato
    if 'results' in data_request:
        # Dati forniti dal frontend
        final = data_request.get('results')
        trajectory = data_request.get('trajectory', [])
        velocity = data_request.get('velocity', [])
        settings = data_request.get('settings', {})
    else:
        # Usa dati dallo stato globale (compatibilità con vecchio comportamento)
        final = get_state('final_results')
        if not final: return jsonify({'success': False, 'error': 'Nessun risultato'})
        trajectory = get_state('trajectory_data')
        velocity = get_state('velocity_data')
        settings = {'mass': get_state('body_mass_kg'), 'fps': get_state('fps')}
    
    # Crea il percorso: %appdata%/Kin.ai/test_results/{testId}
    save_dir = os.path.expanduser(f'~\\AppData\\Roaming\\Kin.ai\\test_results\\{test_id}')
    os.makedirs(save_dir, exist_ok=True)
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'testId': test_id,
        'results': final,
        'trajectory': trajectory,
        'velocity': velocity,
        'settings': settings
    }
    
    with open(os.path.join(save_dir, 'results.json'), 'w') as f:
        json.dump(data, f, indent=2)
        
    return jsonify({'success': True, 'path': save_dir})

@app.route('/api/video/info', methods=['GET'])
def video_info():
    path = get_state('video_path')
    return jsonify({
        'success': True, 
        'video_path': os.path.basename(path) if path else None,
        'total_frames': get_state('total_frames'),
        'fps': get_state('fps')
    })

if __name__ == '__main__':
    print("🚀 Server Jump Analysis (Physics Mode) avviato")
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)