"""Audio exists only in this disposable process. Hard 12 s stream lifetime."""
import json
import sys
import struct
import time
import numpy as np
from .engines import ROOT
from moonshine_voice import Transcriber, ModelArch
from moonshine_voice.transcriber import TranscriptEventListener
config = json.loads((ROOT / 'models' / 'asr.json').read_text())
options={'log_api_calls': 'false', 'identify_speakers': 'false'}
if '--speakers' in sys.argv and (ROOT / 'models/diarization.json').exists():
    options.update({'identify_speakers':'true', 'diarization_model_dir':json.loads((ROOT / 'models/diarization.json').read_text())['path'], 'diarization_cluster_window_sec':'12'})
transcriber = Transcriber(config['path'], ModelArch(config['arch']), update_interval=0.4, options=options)
print(json.dumps({'ready':True}),flush=True)
serial = 0


def emit(event, final):
    line = event.line
    spans=line.speaker_spans or []
    indices=sorted({span.speaker_index for span in spans})
    speaker=' / '.join(f'Ventana {serial+1} · Persona {index+1}' for index in indices) or 'Sin atribuir'
    overlap=any(a.start_time < b.start_time+b.duration and b.start_time < a.start_time+a.duration and a.speaker_index != b.speaker_index for i,a in enumerate(spans) for b in spans[i+1:])
    data = {'id': f'{serial}-{line.line_id}', 'text': line.text,
            'status': 'final' if final else 'provisional',
            'latency_ms': line.last_transcription_latency_ms,
            'speaker': speaker, 'overlap': overlap, 'start': line.start_time, 'duration': line.duration}
    print(json.dumps(data, ensure_ascii=False), flush=True)
    if line.audio_data is not None:
        line.audio_data.clear()


class Listener(TranscriptEventListener):
    def on_line_text_changed(self, event):
        emit(event, False)
    def on_line_completed(self, event):
        emit(event, True)
    def on_line_speakers_changed(self, event):
        emit(event, event.line.is_complete)


listener = Listener()
stream = None
elapsed = 0
try:
    while True:
        header = sys.stdin.buffer.read(4)
        if len(header) != 4:
            break
        size = struct.unpack('<I', header)[0]
        if size > 32768 or size % 4:
            break
        raw = sys.stdin.buffer.read(size)
        if len(raw) != size:
            break
        samples = np.frombuffer(raw, dtype='<f4').copy()
        if not np.all(np.isfinite(samples)):
            break
        if stream is None:
            stream = transcriber.create_stream(update_interval=0.4)
            stream.add_listener(listener)
            stream.start()
        stream.add_audio(samples.tolist(), 16000)
        elapsed += len(samples) / 16000
        samples.fill(0)
        del raw, samples
        if elapsed >= 12:
            stream.stop()
            stream.close()
            stream = None
            elapsed = 0
            serial += 1
finally:
    if stream is not None:
        stream.close()
    transcriber.close()
