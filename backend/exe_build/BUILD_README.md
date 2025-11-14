# Guida alla Creazione dell'Eseguibile Backend

Questa guida spiega come creare un eseguibile standalone del backend Jump Analyzer.

**IMPORTANTE:** Tutti i file di build sono ora nella cartella `exe_build`. Esegui i comandi da questa cartella.

## Prerequisiti

1. **Installa PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Installa tutte le dipendenze:**
   ```bash
   cd ..  # Torna alla cartella backend
   pip install -r requirements.txt
   ```

## Metodo 1: Usando lo Script di Build (Consigliato)

1. Apri un terminale nella cartella `backend/exe_build`
2. Esegui:
   ```bash
   python build_exe.py
   ```

3. L'eseguibile sarà creato in `backend/exe_build/dist/JumpAnalyzerBackend.exe`

## Metodo 2: Usando il File .spec

1. Apri un terminale nella cartella `backend/exe_build`
2. Esegui:
   ```bash
   pyinstaller JumpAnalyzerBackend.spec
   ```

3. L'eseguibile sarà creato in `backend/exe_build/dist/JumpAnalyzerBackend.exe`

## Metodo 3: Script Batch (Windows)

1. Fai doppio click su `build.bat` nella cartella `exe_build`
2. Attendi il completamento
3. L'eseguibile sarà creato in `backend/exe_build/dist/JumpAnalyzerBackend.exe`

## Struttura Cartelle

```
backend/
├── app.py                    # Script principale
├── contour.py                 # Moduli del backend
├── jump_analyzer.py
├── API_Call.py
├── Kinai_API.py
└── exe_build/                # Cartella per la build
    ├── build_exe.py          # Script di build
    ├── JumpAnalyzerBackend.spec
    ├── build.bat
    ├── BUILD_README.md
    ├── build/                # File temporanei di build (generati)
    └── dist/                 # Eseguibile finale (generato)
        └── JumpAnalyzerBackend.exe
```

## Configurazioni Disponibili

### Mostrare/Nascondere la Console

Nel file `JumpAnalyzerBackend.spec`, modifica la riga:
```python
console=True,  # True = mostra console, False = nasconde
```

Oppure nel file `build_exe.py`, cambia:
```python
'--console',  # in '--windowed' per nascondere
```

### Aggiungere un'Icona

Nel file `JumpAnalyzerBackend.spec`, modifica:
```python
icon='path/to/icon.ico',
```

## Dopo la Build

1. **Crea la cartella uploads:**
   - L'eseguibile creerà automaticamente la cartella `uploads` se non esiste
   - Oppure creala manualmente nella stessa directory dell'eseguibile

2. **Testa l'eseguibile:**
   - Esegui `JumpAnalyzerBackend.exe` dalla cartella `exe_build/dist`
   - Dovrebbe avviare il server Flask su `http://0.0.0.0:5000`

3. **Distribuzione:**
   - Copia solo l'eseguibile (è standalone, contiene tutto)
   - Assicurati che la cartella `uploads` esista o verrà creata automaticamente

## Risoluzione Problemi

### Errore: "ModuleNotFoundError"

Se mancano moduli, aggiungili a `hiddenimports` nel file `JumpAnalyzerBackend.spec`:
```python
hiddenimports=[
    # ... moduli esistenti ...
    'nome_modulo_mancante',
],
```

### Errore: "MediaPipe non trovato"

Assicurati di includere:
```python
'--collect-all=mediapipe',
'--collect-submodules=mediapipe',
```

### File troppo grande

Se l'eseguibile è troppo grande, puoi:
1. Usare `--onedir` invece di `--onefile` (crea una cartella con più file)
2. Usare UPX per comprimere (già abilitato nel .spec)

### Antivirus segnala l'eseguibile

Gli eseguibili PyInstaller possono essere segnalati come falsi positivi. Puoi:
1. Aggiungere una firma digitale (richiede certificato)
2. Segnalare come falso positivo all'antivirus

## Note Importanti

- L'eseguibile è specifico per il sistema operativo su cui è stato creato
- Su Windows crea un `.exe`, su Linux/Mac crea un eseguibile senza estensione
- La prima esecuzione può essere più lenta (estrazione file temporanei)
- I file temporanei vengono estratti in una cartella temporanea del sistema
- I file di build e l'eseguibile sono separati dal codice sorgente nella cartella `exe_build`


