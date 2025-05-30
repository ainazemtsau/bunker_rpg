@echo off
echo Starting Flask SocketIO backend...
start cmd /k "cd /d %~dp0 && venv\Scripts\activate && python app.py"

echo Starting React frontend...
timeout /t 3 > nul
start cmd /k "cd /d %~dp0\frontend && npm start"

echo Both servers starting...
echo.
echo Backend will be available at: http://localhost:5000
echo Frontend will be available at: http://localhost:3000
echo.
echo For local network access, replace 'localhost' with your IP address
echo To find your IP address, run: ipconfig
echo.
pause