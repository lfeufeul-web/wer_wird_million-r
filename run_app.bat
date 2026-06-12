@echo off
set "PYTHON_EXE=C:\Users\maxim\AppData\Local\Programs\Python\Python312\python.exe"
"%PYTHON_EXE%" -m pip install -r requirements.txt
"%PYTHON_EXE%" -m flet run main-DESKTOP-3SJ00FD.py
pause
