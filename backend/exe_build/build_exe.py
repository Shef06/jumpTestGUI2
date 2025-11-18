"""
Script per creare l'eseguibile del backend usando PyInstaller
Esegui questo script dalla cartella exe_build
"""
import PyInstaller.__main__
import os
import sys

# Ottieni il percorso della directory backend (parent di exe_build)
exe_build_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(exe_build_dir)  # Cartella backend

# Determina il separatore per --add-data (; su Windows, : su Linux/Mac)
separator = ';' if sys.platform == 'win32' else ':'

# Configurazione PyInstaller
# I percorsi sono relativi alla cartella backend
args = [
    os.path.join(backend_dir, 'app.py'),  # Script principale (nella cartella backend)
    '--name=JumpAnalyzerBackend',  # Nome dell'eseguibile
    '--onefile',  # Crea un singolo file eseguibile
    '--console',  # Mostra la console (cambia in --windowed per nasconderla)
    f'--add-data={os.path.join(backend_dir, "contour.py")}{separator}.',  # Includi i moduli necessari
    f'--add-data={os.path.join(backend_dir, "jump_analyzer.py")}{separator}.',
    '--hidden-import=flask',
    '--hidden-import=flask_cors',
    '--hidden-import=cv2',
    '--hidden-import=mediapipe',
    '--hidden-import=numpy',
    '--hidden-import=werkzeug',
    '--hidden-import=contour',
    '--hidden-import=jump_analyzer',
    '--hidden-import=API_Call',
    '--hidden-import=Kinai_API',
    '--collect-all=mediapipe',  # Raccogli tutti i file di MediaPipe
    '--collect-all=opencv-python',  # Raccogli tutti i file di OpenCV
    '--collect-submodules=mediapipe',  # Includi tutti i sottomoduli
    '--noconfirm',  # Non chiedere conferma per sovrascrivere
    '--clean',  # Pulisci i file temporanei prima di buildare
    '--workpath', os.path.join(exe_build_dir, 'build'),  # Cartella build in exe_build
    '--distpath', os.path.join(exe_build_dir, 'dist'),  # Cartella dist in exe_build
]

# Cambia directory di lavoro alla cartella backend (dove si trova app.py)
os.chdir(backend_dir)

print("Avvio build dell'eseguibile...")
print(f"Directory backend: {backend_dir}")
print(f"Directory build: {exe_build_dir}\n")

# Esegui PyInstaller
try:
    PyInstaller.__main__.run(args)
    print("\n[OK] Build completata!")
    exe_name = 'JumpAnalyzerBackend.exe' if sys.platform == 'win32' else 'JumpAnalyzerBackend'
    exe_path = os.path.join(exe_build_dir, 'dist', exe_name)
    print(f"L'eseguibile si trova in: {exe_path}")
    print("\nNOTA: La cartella 'uploads' verra creata automaticamente all'avvio se non esiste")
except Exception as e:
    print(f"\n[ERRORE] Errore durante la build: {e}")
    sys.exit(1)


