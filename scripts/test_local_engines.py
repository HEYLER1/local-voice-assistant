"""Synthetic Spanish audio in RAM; not a measurement of the user's accent."""
import sys
import json
import subprocess
import time
from pathlib import Path
import numpy as np
from moonshine_voice import Transcriber, ModelArch
from moonshine_voice.transcriber import TranscriptEventListener
ROOT = Path(__file__).resolve().parent.parent
import io, wave
p = subprocess.run([sys.executable, '-m', 'assistant.tts_worker'],
    input=json.dumps({'text':'Mañana entrego los ejercicios de cálculo. No, el viernes.'}).encode(),
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, cwd=ROOT)
if p.returncode or not p.stdout:
    print('Falló síntesis',p.returncode,p.stderr.decode()[-1000:]);sys.exit(1)
with wave.open(io.BytesIO(p.stdout)) as wav:
    rate=wav.getframerate()
    audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
samples=np.interp(np.arange(int(len(audio)*16000/rate))*rate/16000,np.arange(len(audio)),audio).astype(np.float32)
audio.fill(0);del audio,p
config=json.loads((ROOT/'models/asr.json').read_text())
t=Transcriber(config['path'],ModelArch(config['arch']))
partials=[];finals=[]
class Listener(TranscriptEventListener):
    def on_line_text_changed(self,e): partials.append(e.line.text)
    def on_line_completed(self,e): finals.append(e.line.text)
t.add_listener(Listener());t.start()
start=time.monotonic()
for i in range(0,len(samples),3200): t.add_audio(samples[i:i+3200].tolist(),16000)
t.add_audio([0.0]*16000,16000);t.stop();t.get_default_stream().close();t.close()
print(json.dumps({'synthetic_test':True,'partials':len(partials),'finals':finals,'processing_seconds':round(time.monotonic()-start,3)},ensure_ascii=False))
# Fingerprint engine real inference, never compare identities from synthetic data.
p=subprocess.run([sys.executable,'-m','assistant.speaker_worker'],input=samples[:128000].tobytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
if p.returncode: print('Huella: falló motor',p.returncode,p.stderr.decode()[-1000:]);sys.exit(1)
f=json.loads(p.stdout)
print('Huella: vector real de',len(f['vector']),'dimensiones; calidad',f['quality'])

import struct
stream_audio=np.concatenate([samples,np.zeros(16000,dtype=np.float32)])
packets=b''.join(struct.pack('<I',len(chunk.tobytes()))+chunk.tobytes() for chunk in [stream_audio[i:i+3200] for i in range(0,len(stream_audio),3200)])
p=subprocess.run([sys.executable,'-m','assistant.asr_worker','--speakers'],input=packets,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
samples.fill(0);stream_audio.fill(0);del packets
if p.returncode: print('Diarización falló',p.returncode,p.stderr.decode()[-1000:]);sys.exit(1)
events=[json.loads(line) for line in p.stdout.splitlines()]
print('Adaptador streaming real:',len(events),'eventos; etiquetas:',sorted({e.get('speaker','') for e in events if e.get('speaker')}))
