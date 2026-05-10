@echo off
title Battle City - AL2002 AI Lab
color 0A
echo.
echo  ========================================
echo   BATTLE CITY - AL2002 AI Lab
echo  ========================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from python.org
    echo  Make sure to CHECK "Add Python to PATH" during install.
    pause & exit /b 1
)
python -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo  Installing pygame...
    pip install pygame --quiet
)
cd /d "%~dp0"
echo  Starting game...
python main.py
if errorlevel 1 ( echo. & echo  [ERROR] Game crashed. & pause )
