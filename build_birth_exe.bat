@echo off
chcp 65001 > nul
rem 대한민국 출생 통계 분석기를 단일 실행파일(dist\BirthAnalyzer.exe)로 빌드
cd /d "%~dp0"
python -m pip install -q PyQt6 pandas matplotlib openpyxl pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name BirthAnalyzer ^
    --exclude-module tkinter ^
    --exclude-module pygame ^
    --exclude-module PyQt5 ^
    --exclude-module PySide6 ^
    --exclude-module IPython ^
    --exclude-module PyQt6.QtWebEngineCore ^
    --exclude-module PyQt6.QtQml ^
    --exclude-module PyQt6.QtQuick ^
    --exclude-module PyQt6.QtMultimedia ^
    --exclude-module PyQt6.QtBluetooth ^
    birth_gui.py
echo.
echo 빌드 완료: dist\BirthAnalyzer.exe
