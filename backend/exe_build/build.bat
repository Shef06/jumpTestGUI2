@echo off
REM Script batch per creare l'eseguibile su Windows
REM Esegui questo script dalla cartella exe_build
echo ========================================
echo  Build JumpAnalyzerBackend Executable
echo ========================================
echo.

REM Verifica che Python sia installato
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Python non trovato!
    echo Installa Python e riprova.
    pause
    exit /b 1
)

REM Verifica che PyInstaller sia installato
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller non trovato. Installazione in corso...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERRORE: Impossibile installare PyInstaller
        pause
        exit /b 1
    )
)

REM Esegui lo script di build
echo Avvio build...
python build_exe.py

if errorlevel 1 (
    echo.
    echo ERRORE durante la build!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build completata con successo!
echo ========================================
echo.
echo L'eseguibile si trova in: dist\JumpAnalyzerBackend.exe
echo.
pause


