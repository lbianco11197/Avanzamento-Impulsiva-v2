@echo off
echo Avvio portale Streamlit - Euroirte s.r.l.
echo --------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo Python non trovato. Assicurati che sia installato.
    pause
    exit /b
)

echo Avvio dell'app...
cmd /k python streamlit_tecnici_finale.py
