#!/bin/zsh
set -e
cd "${0:A:h}"
PYTHON_BIN="${ASSISTANT_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  print 'Se necesita Python 3.13. Define ASSISTANT_PYTHON con su ruta.'
  exit 1
fi
"$PYTHON_BIN" -m venv .venv
.venv/bin/pip install -r requirements.lock
# Both packages provide the same import; the maintained wheel must be installed last.
.venv/bin/pip install --force-reinstall --no-deps webrtcvad-wheels==2.0.14.post1
.venv/bin/python scripts/download_models.py
.venv/bin/python scripts/download_voice.py
.venv/bin/python scripts/download_diarization.py
print 'Instalación completa. Abre run.command y visita http://127.0.0.1:8765.'
