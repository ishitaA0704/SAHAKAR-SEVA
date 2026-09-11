@echo off
echo =======================================================
echo    Starting Sahakar Seva Terminal...
echo =======================================================

echo 1. Starting Flask Server (app.py)
start "Sahakar Seva - Server" cmd /k "python app.py"

echo 2. Starting Hardware Button Listener...
start "Sahakar Seva - Hardware Client" cmd /k "python external_push_button.py"

echo =======================================================
echo Both programs are now running in separate windows!
echo Please open your browser to: http://127.0.0.1:5000
echo =======================================================
