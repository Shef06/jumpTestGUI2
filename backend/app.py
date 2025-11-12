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
    'person_height_cm': 170.0,
    'body_mass_kg': 70.0,
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
        'jump_detected': analyzer.jump_started
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


@app.route('/api/analysis/results', methods=['GET'])
def analysis_results():
    """Risultati finali"""
    final_results = get_state('final_results')
    if final_results:
        return jsonify({
            'success': True,
            'results': final_results,
            'trajectory': get_state('trajectory_data'),
            'velocity': get_state('velocity_data')
        })
    return jsonify({'success': False, 'error': 'Analisi non completata'})


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
    """Salva risultati in file JSON"""
    try:
        final_results = get_state('final_results')
        if not final_results:
            return jsonify({'success': False, 'error': 'Nessun risultato da salvare'})
        
        save_dir = os.path.expanduser('~\\AppData\\Roaming\\Kin.ai\\last_jump')
        os.makedirs(save_dir, exist_ok=True)
        
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'results': final_results,
            'trajectory': get_state('trajectory_data'),
            'velocity': get_state('velocity_data'),
            'settings': {
                'fps': get_state('fps'),
                'person_height_cm': get_state('person_height_cm'),
                'body_mass_kg': get_state('body_mass_kg')
            }
        }
        
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
    import webbrowser
    import threading
    from pathlib import Path
    
    # Determina il percorso assoluto del file index.html
    backend_dir = Path(__file__).parent
    frontend_dist = backend_dir.parent / 'frontend' / 'dist' / 'index.html'
    
    # Funzione per aprire il browser dopo un breve delay
    def open_browser():
        import time
        time.sleep(1.5)  # Attendi che il server sia avviato
        if frontend_dist.exists():
            file_url = frontend_dist.as_uri()
            print(f"\n🌐 Apertura browser: {file_url}\n")
            webbrowser.open(file_url)
        else:
            print(f"\n⚠️  File index.html non trovato in: {frontend_dist}")
            print("   Esegui prima 'npm run build' nella cartella frontend\n")
    
    # Avvia il thread per aprire il browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("🚀 Avvio server Flask su http://0.0.0.0:5000")
    print("   Il browser si aprirà automaticamente tra pochi secondi...")
    
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)