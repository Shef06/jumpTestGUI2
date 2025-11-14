# -*- mode: python ; coding: utf-8 -*-
"""
File di configurazione PyInstaller per JumpAnalyzerBackend
Esegui questo file dalla cartella exe_build:
    pyinstaller JumpAnalyzerBackend.spec
"""
import os
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

# Ottieni il percorso della directory backend (parent di exe_build)
# PyInstaller fornisce SPECPATH che punta al file .spec corrente
try:
    exe_build_dir = os.path.dirname(os.path.abspath(SPECPATH))
except NameError:
    # Fallback: assume che lo script venga eseguito da exe_build
    exe_build_dir = os.getcwd()
backend_dir = os.path.dirname(exe_build_dir)

# Configurazione dei dati e moduli
datas = [
    (os.path.join(backend_dir, 'contour.py'), '.'),
    (os.path.join(backend_dir, 'jump_analyzer.py'), '.'),
    (os.path.join(backend_dir, 'API_Call.py'), '.'),
    (os.path.join(backend_dir, 'Kinai_API.py'), '.')
]
binaries = []
hiddenimports = ['flask', 'flask_cors', 'cv2', 'mediapipe', 'numpy', 'werkzeug', 'contour', 'jump_analyzer', 'API_Call', 'Kinai_API']
hiddenimports += collect_submodules('mediapipe')
tmp_ret = collect_all('mediapipe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('opencv-python')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    [os.path.join(backend_dir, 'app.py')],  # Script principale nella cartella backend
    pathex=[backend_dir],  # Aggiungi backend_dir al path
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JumpAnalyzerBackend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Cambia in False per nascondere la console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Puoi aggiungere un'icona: icon='path/to/icon.ico'
)

