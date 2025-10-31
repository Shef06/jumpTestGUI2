# Jump Analyzer Pro - Flask + Svelte

Sistema professionale per l'analisi biomeccanica del salto verticale, completamente riscritto con backend Flask e frontend Svelte.

## 📁 Struttura del Progetto

```
jump-analyzer-pro/
├── backend/
│   ├── app.py                  # Server Flask con API REST
│   ├── contour.py              # Rilevamento contorni corpo
│   ├── jump_analyzer.py        # Logica analisi salto
│   ├── requirements.txt        # Dipendenze Python
│   └── uploads/                # Directory video caricati
└── frontend/
    ├── src/
    │   ├── App.svelte          # Componente principale
    │   ├── main.js             # Entry point
    │   ├── app.css             # Stili globali Tailwind
    │   └── lib/
    │       ├── VideoPlayer.svelte    # Player video
    │       ├── StepHolder.svelte     # Gestione step
    │       ├── ResultsView.svelte    # Visualizzazione risultati
    │       └── stores.js             # Store Svelte
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── postcss.config.js
```

## 🚀 Installazione e Avvio

### Backend (Flask)

1. **Navigare nella directory backend**:
```bash
cd backend
```

2. **Creare ambiente virtuale**:
```bash
python -m venv venv
```

3. **Attivare ambiente virtuale**:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. **Installare dipendenze**:
```bash
pip install -r requirements.txt
```

5. **Avviare server Flask**:
```bash
python app.py
```

Il backend sarà disponibile su `http://localhost:5000`

### Frontend (Svelte)

1. **Navigare nella directory frontend** (in un nuovo terminale):
```bash
cd frontend
```

2. **Installare dipendenze**:
```bash
npm install
```

3. **Avviare server di sviluppo**:
```bash
npm run dev
```

Il frontend sarà disponibile su `http://localhost:3000`

## 🎯 Flusso dell'Applicazione

### Step 1: Caricamento Video
- **Carica Video**: Upload di file video dal computer
- **Registra Video**: Registrazione diretta dalla webcam
- Formati supportati: MP4, AVI, MOV, MKV, WMV

### Step 2: Calibrazione Sistema
- **FPS Video**: Inserimento manuale dei frame per secondo
- **Altezza Persona**: Altezza reale in cm (100-250)
- **Massa Corporea**: Peso in kg (40-150)
- Il sistema calibra automaticamente il rapporto pixel-cm analizzando la persona in posizione eretta

### Step 3: Analisi Salto
- Avvio analisi automatica del video
- Visualizzazione real-time di:
  - Altezza corrente
  - Altezza massima
  - Velocità di decollo
  - Potenza stimata
- Controlli disponibili:
  - Pausa/Riprendi analisi

### Step 4: Visualizzazione Risultati
Risultati finali dell'analisi con:

#### Metriche Principali
- **Altezza Massima**: Altezza massima raggiunta in cm
- **Tempo di Volo**: Durata totale del salto in secondi
- **Velocità Decollo**: Velocità al momento del decollo in cm/s
- **Potenza Stimata**: Potenza sviluppata in Watt

#### Analisi Fasi
- **Tempo Contatto**: Durata contatto piedi-suolo
- **Fase Eccentrica**: Durata fase di caricamento
- **Fase Concentrica**: Durata fase di spinta
- **Tempo Caduta**: Durata della discesa

#### Parametri Biomeccanici
- **Forza Media**: Forza media applicata in Newton
- **Stato Salto**: Conferma rilevamento salto

#### Grafici
- **Traiettoria del Salto**: Grafico altezza vs tempo
- **Velocità nel Tempo**: Grafico velocità vs tempo

## 🔌 API REST Endpoints

### Video Management
- `GET /api/cameras` - Lista webcam disponibili
- `POST /api/video/upload` - Upload video file
- `POST /api/recording/start` - Avvia registrazione
- `POST /api/recording/stop` - Ferma registrazione
- `GET /api/video/frame` - Ottieni frame corrente

### Settings
- `POST /api/settings/camera` - Imposta camera index
- `POST /api/settings/fps` - Imposta FPS video
- `POST /api/settings/height` - Imposta altezza persona
- `POST /api/settings/mass` - Imposta massa corporea

### Calibration
- `POST /api/calibration/start` - Avvia calibrazione
- `GET /api/calibration/status` - Stato calibrazione

### Analysis
- `POST /api/analysis/start` - Avvia analisi
- `GET /api/analysis/status` - Stato analisi
- `GET /api/analysis/data` - Dati real-time
- `GET /api/analysis/results` - Risultati finali
- `POST /api/analysis/pause` - Pausa analisi
- `POST /api/analysis/resume` - Riprendi analisi
- `POST /api/analysis/stop` - Ferma analisi
- `POST /api/analysis/retry` - Ripeti test

## 🛠️ Tecnologie Utilizzate

### Backend
- **Flask**: Framework web Python
- **OpenCV**: Elaborazione video e computer vision
- **MediaPipe**: Rilevamento pose e segmentazione corpo
- **NumPy**: Calcoli scientifici

### Frontend
- **Svelte**: Framework JavaScript reattivo
- **Vite**: Build tool e dev server
- **Tailwind CSS**: Framework CSS utility-first
- **Canvas API**: Rendering grafici personalizzati

## 📊 Comunicazione Frontend-Backend

Il frontend Svelte comunica con il backend Flask tramite:

1. **Fetch API**: Chiamate HTTP REST
2. **Polling**: Aggiornamenti periodici (100ms) per frame video e dati real-time
3. **JSON**: Formato dati per tutte le comunicazioni

### Esempio chiamata API:
```javascript
const response = await fetch('http://localhost:5000/api/analysis/start', {
  method: 'POST'
});
const data = await response.json();
```

## 🎨 Design e UI

L'interfaccia è stata progettata seguendo principi moderni:
- **Layout responsive**: Adattamento automatico a schermi diversi
- **Design scuro**: Minore affaticamento visivo
- **Gradienti colorati**: Elementi distintivi e accattivanti
- **Animazioni fluide**: Transizioni smooth tra stati
- **Feedback visivo**: Indicatori di stato chiari

## 📝 Note Tecniche

### Performance
- Il polling a 100ms garantisce aggiornamenti fluidi senza sovraccaricare il sistema
- I frame video sono codificati in JPEG base64 per il trasferimento
- L'analisi avviene in thread separati per non bloccare il server

### Calibrazione
- La calibrazione con altezza persona usa segmentazione MediaPipe per rilevare testa e piedi
- Il rapporto pixel-cm viene calcolato confrontando l'altezza reale con quella in pixel
- La baseline del bacino viene calibrata sui primi 30 frame statici

### Analisi Biomeccanica
- Le fasi (eccentrica, concentrica) sono rilevate tramite analisi della velocità
- La potenza è stimata considerando energia cinetica e potenziale
- La forza media è calcolata dall'impulso durante la fase di contatto

## 🔧 Troubleshooting

### Backend non si avvia
- Verificare che tutte le dipendenze siano installate
- Controllare che la porta 5000 sia disponibile
- Verificare che l'ambiente virtuale sia attivato

### Frontend non si connette al backend
- Verificare che il backend sia in esecuzione su localhost:5000
- Controllare la console browser per errori CORS
- Verificare la configurazione proxy in vite.config.js

### Calibrazione fallisce
- Assicurarsi che la persona sia completamente visibile nel frame
- La persona deve essere in posizione eretta e ferma
- Verificare che l'illuminazione sia adeguata

### Video non viene caricato
- Verificare il formato del file (deve essere MP4, AVI, MOV, MKV o WMV)
- Controllare che il file non sia corrotto
- Verificare che il file non superi 500MB

## 📄 Licenza

Questo progetto è una conversione completa da Eel a Flask + Svelte del sistema Jump Analyzer originale.

## 👥 Supporto

Per problemi o domande, consultare la documentazione delle tecnologie utilizzate:
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Svelte Documentation](https://svelte.dev/)
- [MediaPipe Documentation](https://google.github.io/mediapipe/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)#
