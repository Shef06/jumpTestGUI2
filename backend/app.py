"""
Flask Backend per Jump Analyzer Pro
API REST per analisi salto in alto
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
from contour import get_head_y
from jump_analyzer import JumpAnalyzer

app = Flask(__name__)
CORS(app)

# Configurazione upload
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Inizializzazione Mediapipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Stato applicazione
app_state = {
    'video_path': None,
    'is_recording': False,
    'is_analyzing': False,
    'is_calibrating': False,
    'is_paused': False,
    'step_mode': False,
    'current_frame': 0,
    'total_frames': 0,
    'cap': None,
    'analyzer': None,
    'video_writer': None,
    'person_height_cm': 170.0,
    'body_mass_kg': 70.0,
    'fps': 30,
    'camera_index': 0,
    'current_video_frame': None,
    'realtime_data': {},
    'trajectory_data': [],
    'velocity_data': [],
    'analysis_thread': None
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """Ottiene lista webcam disponibili"""
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(i)
            cap.release()
    return jsonify({'cameras': cameras if cameras else [0]})


@app.route('/api/settings/camera', methods=['POST'])
def set_camera():
    """Imposta camera index"""
    data = request.json
    app_state['camera_index'] = data.get('index', 0)
    return jsonify({'success': True})


@app.route('/api/settings/fps', methods=['POST'])
def set_fps():
    """Imposta FPS"""
    data = request.json
    try:
        fps = int(data.get('fps', 30))
        if 1 <= fps <= 240:
            app_state['fps'] = fps
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
            app_state['person_height_cm'] = height
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
            app_state['body_mass_kg'] = mass
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Massa deve essere tra 40 e 150 kg'})
    except:
        return jsonify({'success': False, 'error': 'Valore non valido'})


@app.route('/api/video/upload', methods=['POST'])
def upload_video():
    """Upload video file"""
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
        file.save(filepath)
        
        # Verifica che il video sia valido
        test_cap = cv2.VideoCapture(filepath)
        if test_cap.isOpened():
            app_state['video_path'] = filepath
            fps = test_cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            test_cap.release()
            return jsonify({
                'success': True,
                'video_path': filename,
                'fps': fps,
                'total_frames': total_frames
            })
        else:
            os.remove(filepath)
            return jsonify({'success': False, 'error': 'File video non valido'})
    
    return jsonify({'success': False, 'error': 'Formato file non supportato'})


@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    """Avvia registrazione webcam"""
    if app_state['is_recording']:
        return stop_recording()
    
    camera_index = app_state['camera_index']
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        return jsonify({'success': False, 'error': f'Impossibile aprire camera {camera_index}'})
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"recording_{timestamp}.mp4"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(filepath, fourcc, app_state['fps'], (width, height))
    
    app_state['video_path'] = filepath
    app_state['cap'] = cap
    app_state['video_writer'] = video_writer
    app_state['is_recording'] = True
    app_state['record_start_time'] = time.time()
    
    # Avvia thread registrazione
    thread = threading.Thread(target=recording_loop)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Registrazione avviata'})


def recording_loop():
    """Loop registrazione video"""
    while app_state['is_recording'] and app_state['cap'] and app_state['cap'].isOpened():
        ret, frame = app_state['cap'].read()
        if not ret:
            break
        
        elapsed = time.time() - app_state['record_start_time']
        cv2.putText(frame, f"REC {elapsed:.1f}s", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        cv2.circle(frame, (frame.shape[1] - 40, 40), 15, (0, 0, 255), -1)
        
        app_state['video_writer'].write(frame)
        
        # Salva frame corrente per streaming
        _, buffer = cv2.imencode('.jpg', frame)
        app_state['current_video_frame'] = base64.b64encode(buffer).decode('utf-8')
        
        time.sleep(0.03)


@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    """Ferma registrazione"""
    app_state['is_recording'] = False
    
    if app_state['cap']:
        app_state['cap'].release()
    if app_state['video_writer']:
        app_state['video_writer'].release()
    
    filename = os.path.basename(app_state['video_path']) if app_state['video_path'] else None
    
    return jsonify({
        'success': True,
        'message': 'Registrazione completata',
        'video_path': filename
    })


@app.route('/api/video/frame', methods=['GET'])
def get_video_frame():
    """Ottiene frame corrente del video"""
    if app_state['current_video_frame']:
        return jsonify({
            'success': True,
            'frame': app_state['current_video_frame']
        })
    return jsonify({'success': False})


@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    """Avvia calibrazione"""
    if not app_state['video_path'] or not os.path.exists(app_state['video_path']):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})
    
    app_state['is_calibrating'] = True
    app_state['analyzer'] = JumpAnalyzer(fps=app_state['fps'])
    
    # Avvia thread calibrazione
    thread = threading.Thread(target=calibration_loop)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Calibrazione avviata'})


def calibration_loop():
    """Loop calibrazione"""
    cap = cv2.VideoCapture(app_state['video_path'])
    
    if not cap.isOpened():
        app_state['is_calibrating'] = False
        return
    
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    calibration_success = False
    frames_checked = 0
    max_frames = int(app_state['fps'] * 5)
    
    with mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as pose:
        
        while cap.isOpened() and app_state['is_calibrating'] and frames_checked < max_frames:
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
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                success = app_state['analyzer'].calibrate_with_person_height(
                    app_state['person_height_cm'],
                    results.pose_landmarks,
                    frame_height,
                    frame=image
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
            
            cv2.putText(image, f"Frame: {frames_checked}/{max_frames}", (10, frame_height - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Salva frame
            _, buffer = cv2.imencode('.jpg', image)
            app_state['current_video_frame'] = base64.b64encode(buffer).decode('utf-8')
            
            if calibration_success:
                time.sleep(2)
                break
            
            time.sleep(0.03)
    
    cap.release()
    app_state['is_calibrating'] = False
    app_state['calibration_result'] = {
        'success': calibration_success,
        'ratio': app_state['analyzer'].pixel_to_cm_ratio if calibration_success else None,
        'height': app_state['person_height_cm'] if calibration_success else None
    }


@app.route('/api/calibration/status', methods=['GET'])
def calibration_status():
    """Stato calibrazione"""
    if 'calibration_result' in app_state:
        result = app_state['calibration_result']
        del app_state['calibration_result']
        return jsonify(result)
    return jsonify({
        'success': app_state['is_calibrating'],
        'in_progress': app_state['is_calibrating']
    })


@app.route('/api/analysis/start', methods=['POST'])
def start_analysis():
    """Avvia analisi"""
    if not app_state['video_path'] or not os.path.exists(app_state['video_path']):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})
    
    if not app_state['analyzer'] or not app_state['analyzer'].calibrated_with_height:
        return jsonify({'success': False, 'error': 'Sistema non calibrato'})
    
    app_state['is_analyzing'] = True
    app_state['trajectory_data'] = []
    app_state['velocity_data'] = []
    app_state['realtime_data'] = {}
    
    # Avvia thread analisi
    thread = threading.Thread(target=analysis_loop)
    thread.daemon = True
    app_state['analysis_thread'] = thread
    thread.start()
    
    return jsonify({'success': True, 'message': 'Analisi avviata'})


def analysis_loop():
    """Loop analisi"""
    cap = cv2.VideoCapture(app_state['video_path'])
    
    if not cap.isOpened():
        app_state['is_analyzing'] = False
        return
    
    app_state['cap'] = cap
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    app_state['total_frames'] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    app_state['current_frame'] = 0
    
    with mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as pose:
        
        while cap.isOpened() and app_state['is_analyzing']:
            if app_state['step_mode'] or app_state['is_paused']:
                time.sleep(0.1)
                continue
            
            ret, frame = cap.read()
            if not ret:
                break
            
            app_state['current_frame'] = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                left_hip = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP]
                right_hip = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_HIP]
                hip_y = ((left_hip.y + right_hip.y) / 2) * frame_height
                
                status, current_height = app_state['analyzer'].process_frame(hip_y)
                
                # Visualizzazioni
                if status == "calibrazione_baseline":
                    cv2.putText(image, "CALIBRAZIONE BASELINE", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                elif status == "analisi":
                    if app_state['analyzer'].jump_started:
                        cv2.putText(image, "SALTO IN CORSO!", (10, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                        cv2.putText(image, f"Altezza: {current_height:.1f} cm", (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                        
                        # Aggiorna dati real-time
                        t_seconds = app_state['analyzer'].current_frame / max(1, app_state['analyzer'].fps)
                        app_state['trajectory_data'].append({
                            't': round(t_seconds, 3),
                            'y': round(current_height, 2)
                        })
                        
                        if len(app_state['analyzer'].hip_velocities) > 0:
                            app_state['velocity_data'].append({
                                't': round(t_seconds, 3),
                                'v': round(app_state['analyzer'].hip_velocities[-1], 2)
                            })
                        
                        app_state['realtime_data'] = {
                            'current_height': round(current_height, 1),
                            'max_height': round(app_state['analyzer'].max_jump_height_cm, 1),
                            'takeoff_velocity': round(app_state['analyzer'].get_takeoff_velocity(), 1),
                            'estimated_power': round(app_state['analyzer'].get_estimated_power(app_state['body_mass_kg']), 1)
                        }
            
            # Salva frame
            _, buffer = cv2.imencode('.jpg', image)
            app_state['current_video_frame'] = base64.b64encode(buffer).decode('utf-8')
            
            time.sleep(0.01)
    
    cap.release()
    app_state['cap'] = None
    app_state['is_analyzing'] = False
    
    # Prepara risultati finali
    app_state['final_results'] = {
        'max_height': round(app_state['analyzer'].max_jump_height_cm, 2),
        'flight_time': round(app_state['analyzer'].get_flight_time(), 3),
        'fall_time': round(app_state['analyzer'].get_fall_time(), 3),
        'contact_time': round(app_state['analyzer'].get_contact_time(), 3),
        'eccentric_time': round(app_state['analyzer'].get_eccentric_time(), 3),
        'concentric_time': round(app_state['analyzer'].get_concentric_time(), 3),
        'takeoff_velocity': round(app_state['analyzer'].get_takeoff_velocity(), 2),
        'estimated_power': round(app_state['analyzer'].get_estimated_power(app_state['body_mass_kg']), 1),
        'average_force': round(app_state['analyzer'].get_average_force(app_state['body_mass_kg']), 1),
        'jump_detected': app_state['analyzer'].jump_started
    }


@app.route('/api/analysis/status', methods=['GET'])
def analysis_status():
    """Stato analisi"""
    return jsonify({
        'is_analyzing': app_state['is_analyzing'],
        'is_paused': app_state['is_paused'],
        'current_frame': app_state['current_frame'],
        'total_frames': app_state['total_frames']
    })


@app.route('/api/analysis/data', methods=['GET'])
def analysis_data():
    """Dati real-time analisi"""
    return jsonify({
        'realtime': app_state.get('realtime_data', {}),
        'trajectory': app_state.get('trajectory_data', []),
        'velocity': app_state.get('velocity_data', [])
    })


@app.route('/api/analysis/results', methods=['GET'])
def analysis_results():
    """Risultati finali"""
    if 'final_results' in app_state:
        results = app_state['final_results']
        return jsonify({
            'success': True,
            'results': results,
            'trajectory': app_state.get('trajectory_data', []),
            'velocity': app_state.get('velocity_data', [])
        })
    return jsonify({'success': False, 'error': 'Analisi non completata'})


@app.route('/api/analysis/pause', methods=['POST'])
def pause_analysis():
    """Pausa analisi"""
    if app_state['is_analyzing']:
        app_state['is_paused'] = True
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/analysis/resume', methods=['POST'])
def resume_analysis():
    """Riprendi analisi"""
    if app_state['is_analyzing']:
        app_state['is_paused'] = False
        app_state['step_mode'] = False
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/analysis/stop', methods=['POST'])
def stop_analysis():
    """Ferma analisi"""
    app_state['is_analyzing'] = False
    app_state['is_paused'] = False
    return jsonify({'success': True})


@app.route('/api/analysis/retry', methods=['POST'])
def retry_analysis():
    """Ripeti test"""
    if app_state['analyzer'] and app_state['analyzer'].calibrated_with_height:
        app_state['analyzer'].reset_keep_calibration()
        app_state['is_paused'] = False
        app_state['current_frame'] = 0
        app_state['trajectory_data'] = []
        app_state['velocity_data'] = []
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/results/save', methods=['POST'])
def save_results():
    """Salva risultati in file JSON"""
    try:
        if 'final_results' not in app_state:
            return jsonify({'success': False, 'error': 'Nessun risultato da salvare'})
        
        # Crea directory se non esiste
        import os
        save_dir = os.path.expanduser('~\\AppData\\Roaming\\Kin.ai\\last_jump')
        os.makedirs(save_dir, exist_ok=True)
        
        # Prepara dati completi
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'results': app_state['final_results'],
            'trajectory': app_state.get('trajectory_data', []),
            'velocity': app_state.get('velocity_data', []),
            'settings': {
                'fps': app_state.get('fps', 30),
                'person_height_cm': app_state.get('person_height_cm', 170),
                'body_mass_kg': app_state.get('body_mass_kg', 70)
            }
        }
        
        # Salva file
        file_path = os.path.join(save_dir, 'results.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True, 
            'message': 'Risultati salvati con successo',
            'file_path': file_path
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Errore salvataggio: {str(e)}'})


@app.route('/api/video/info', methods=['GET'])
def video_info():
    """Restituisce info sul video corrente (dopo registrazione/upload)."""
    path = app_state.get('video_path')
    total = app_state.get('total_frames', 0)
    fps = app_state.get('fps', 30)
    return jsonify({
        'success': True,
        'video_path': os.path.basename(path) if path else None,
        'total_frames': total,
        'fps': fps
    })


@app.route('/api/video/frame_at', methods=['GET'])
def video_frame_at():
    """Ottiene un frame specifico dal video caricato (solo post-analisi)."""
    try:
        index = int(request.args.get('index', 0))
    except Exception:
        return jsonify({'success': False, 'error': 'Indice non valido'})
    path = app_state.get('video_path')
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'error': 'Nessun video disponibile'})

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return jsonify({'success': False, 'error': 'Impossibile aprire il video'})
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if index < 0:
        index = 0
    if index >= total:
        index = total - 1 if total > 0 else 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ret, frame = cap.read()
    if not ret or frame is None:
        cap.release()
        return jsonify({'success': False, 'error': 'Frame non disponibile'})
    _, buffer = cv2.imencode('.jpg', frame)
    cap.release()
    return jsonify({
        'success': True,
        'frame': base64.b64encode(buffer).decode('utf-8'),
        'index': index,
        'total_frames': total
    })


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)