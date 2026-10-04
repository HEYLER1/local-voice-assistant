#!/bin/zsh
cd "${0:A:h}"
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME="$PWD/models/.hf"
export ASSISTANT_PORT=8765
print "Asistente local: abre http://127.0.0.1:8765. Cierra esta ventana para detenerlo."
exec .venv/bin/python -m uvicorn assistant.api:app --host 127.0.0.1 --port 8765 --no-access-log --log-level warning
