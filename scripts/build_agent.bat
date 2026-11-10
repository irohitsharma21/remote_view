@echo off
REM Package the agent into a single Windows .exe. Run this ON WINDOWS.
REM
REM First edit the bake-in defaults at the top of agent\agent.py:
REM   SERVER_DEFAULT = "wss://your-relay.example.com"
REM   SECRET_DEFAULT = "your-shared-secret"
REM
REM Requires Python + pip on the Windows machine.
cd /d "%~dp0\.."
pip install pyinstaller
pyinstaller --onefile --noconsole --name remote_agent ^
  --collect-submodules pynput ^
  agent\agent.py
echo.
echo Built: dist\remote_agent.exe
