@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ====== 文字化け対策（日本語パス/名前があるなら推奨）======
chcp 65001 >nul

rem ====== このbatがあるフォルダへ移動 ======
cd /d "%~dp0"

rem ====== 設定 ======
set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "SPEC=steam_achievements_exporter.spec"

if not exist "%SPEC%" (
  echo [ERROR] Spec file not found: %SPEC%
  echo Place build.bat next to the .spec file.
  exit /b 1
)

rem ====== venv作成（なければ） ======
if not exist "%PY%" (
  echo [INFO] Creating venv...
  py -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

rem ====== 依存のインストール ======
echo [INFO] Installing/Updating build tools...
"%PY%" -m pip install -U pip >nul
"%PY%" -m pip install -U pyinstaller requests >nul

rem ====== クリーン ======
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

rem ====== specからビルド ======
echo [INFO] Building from spec: %SPEC%
"%PY%" -m PyInstaller "%SPEC%" --noconfirm --clean
if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo [OK] Build finished.
echo Check: dist\
echo.
pause