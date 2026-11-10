@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" goto instalar
where py >nul 2>nul
if errorlevel 1 goto tentar_python
py -3 -m venv .venv
if errorlevel 1 goto erro_python
goto instalar
:tentar_python
where python >nul 2>nul
if errorlevel 1 goto erro_python
python -m venv .venv
if errorlevel 1 goto erro_python
:instalar
echo Preparando o Observatorio Global de Juros...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro_instalacao
echo Abrindo o painel em http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 pause
exit /b
:erro_python
echo Instale Python 3.11 ou mais recente e adicione-o ao PATH.
pause
exit /b 1
:erro_instalacao
echo Nao foi possivel instalar as dependencias. Confira a conexao.
pause
exit /b 1
