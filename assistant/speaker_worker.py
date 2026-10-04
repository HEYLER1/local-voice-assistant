"""Consent-controlled embeddings. Raw audio never written, stdout only derived vector."""
import sys
import json
import hashlib
from pathlib import Path
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
import resemblyzer
raw = sys.stdin.buffer.read(512001)
if len(raw) > 512000 or len(raw) % 4 or len(raw) < 16000 * 4 * 3:
    sys.exit(2)
audio = np.frombuffer(raw, dtype='<f4').copy()
del raw
if not np.all(np.isfinite(audio)) or np.max(np.abs(audio)) > 1.1:
    sys.exit(3)
processed = preprocess_wav(audio, source_sr=16000)
audio.fill(0)
if len(processed) < 16000 * 2:
    sys.exit(4)
encoder = VoiceEncoder(device='cpu', verbose=False)
vector = encoder.embed_utterance(processed)
quality = {'voiced_seconds': len(processed) / 16000, 'calibrated': False}
processed.fill(0)
model_path = Path(resemblyzer.__file__).parent / 'pretrained.pt'
print(json.dumps({'vector': vector.tolist(), 'model_id': 'Resemblyzer-0.1.4/' + hashlib.sha256(model_path.read_bytes()).hexdigest(), 'quality': quality}))
