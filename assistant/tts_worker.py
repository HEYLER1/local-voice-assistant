"""Synthesis output is a RAM WAV, with a hard size limit. No audio files."""
import io
import json
import sys
import wave
import onnxruntime
onnxruntime.disable_telemetry_events()
from piper import PiperVoice
from .engines import ROOT
request = json.load(sys.stdin)
text = request['text'][:2000]
voice = PiperVoice.load(str(ROOT / 'models/piper/es_ES-sharvard-medium.onnx'))
output = io.BytesIO()
with wave.open(output, 'wb') as wav:
    total = 0
    configured = False
    for chunk in voice.synthesize(text):
        if not configured:
            wav.setnchannels(chunk.sample_channels)
            wav.setsampwidth(chunk.sample_width)
            wav.setframerate(chunk.sample_rate)
            configured = True
        total += len(chunk.audio_int16_bytes)
        if total > 8_000_000:
            break
        wav.writeframes(chunk.audio_int16_bytes)
sys.stdout.buffer.write(output.getvalue())
output.close()
