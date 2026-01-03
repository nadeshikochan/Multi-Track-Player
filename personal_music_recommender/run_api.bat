@echo off
setlocal
pushd %~dp0
"D:\program_files\miniconda3\envs\hunyuan_mt\python.exe" -m uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1
popd
pause