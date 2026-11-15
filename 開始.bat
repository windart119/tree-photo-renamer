@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% --version >nul 2>&1
if errorlevel 1 (
  echo 找不到 Python 3.10 或以上。
  echo 請先安裝 https://www.python.org/downloads/ ，安裝時勾選 Add python.exe to PATH。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 正在建立虛擬環境……
  %PY% -m venv .venv
  if errorlevel 1 (
    echo 無法建立虛擬環境。
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
echo 正在安裝套件，第一次可能需要較長時間，請稍候……
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo 套件安裝失敗。請把上面的錯誤訊息傳給我。
  pause
  exit /b 1
)

echo.
echo 程式啟動後會自動開啟瀏覽器；若沒有開啟，請手動前往 http://127.0.0.1:7860
echo 請不要關閉這個視窗。
python app.py
echo.
echo 程式已結束。
pause
