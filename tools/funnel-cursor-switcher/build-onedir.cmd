@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist ".venv-build\Scripts\python.exe" (
    python -m venv ".venv-build" || goto :failed
)
".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt || goto :failed
".venv-build\Scripts\python.exe" prepare_mesa.py || goto :failed
".venv-build\Scripts\python.exe" build_onedir.py || goto :failed

popd
exit /b 0

:failed
popd
exit /b 1
