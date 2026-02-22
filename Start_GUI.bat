@echo off
title Novelpia GUI Setup and Launcher
echo ===================================================
echo     Novelpia Chapter Extractor - Setup ^& Launch
echo ===================================================
echo.
echo Installing required Python packages...
pip install -r requirements.txt
echo.
echo Installing browser binaries for Playwright...
playwright install chromium
echo.
echo ===================================================
echo     Setup Complete! Launching the Application...
echo ===================================================
python gui.py
pause
