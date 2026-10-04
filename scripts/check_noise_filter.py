"""Synthetic effects and Spanish speech in RAM; no claim of source separation."""
import io,json,struct,subprocess,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from assistant.audio_filter import SpeechGate
ROOT=Path(__file__).resolve().parent.parent
p=subprocess.run([sys.executable,'-m','assistant.tts_worker'],input=json.dumps({'text':'Mañana entrego los ejercicios de cálculo. No, el viernes.'}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
assert p.returncode==0,p.stderr.decode()
with wave.open(io.BytesIO(p.stdout)) as w:
    rate=w.getframerate();raw=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
voice=np.interp(np.arange(int(len(raw)*16000/rate))*rate/16000,np.arange(len(raw)),raw).astype(np.float32)
gate=SpeechGate();kept=np.concatenate([gate.filter(voice[i:i+3200]) for i in range(0,len(voice),3200)])
retention=float(np.sum(kept**2)/(np.sum(voice**2)+1e-12))
assert retention>.8,retention
print('Energía de voz conservada:',round(retention*100,1),'%')
t=np.arange(32000)/16000;tone=(.1*np.sin(2*np.pi*440*t)).astype(np.float32)
noise_packets=b''.join(struct.pack('<I',3200*4)+tone[i:i+3200].tobytes() for i in range(0,len(tone),3200))
r=subprocess.run([sys.executable,'-m','assistant.asr_worker'],input=noise_packets,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
assert r.returncode==0,r.stderr.decode()
events=[json.loads(l) for l in r.stdout.splitlines()]
assert not any(e.get('text') for e in events),events
print('Tono sin voz: ninguna transcripción.')
audio=np.concatenate([tone, np.zeros(8000,dtype=np.float32),voice,np.zeros(16000,dtype=np.float32)])
audio=np.pad(audio,(0,max(0,195200-len(audio))))
packets=b''.join(struct.pack('<I',len(c)*4)+c.tobytes() for c in [audio[i:i+3200] for i in range(0,len(audio),3200)])
r=subprocess.run([sys.executable,'-m','assistant.asr_worker'],input=packets,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
assert r.returncode==0,r.stderr.decode()
events=[json.loads(l) for l in r.stdout.splitlines()];text=' '.join(e.get('text','') for e in events)
assert 'cálculo' in text.lower() or 'calculo' in text.lower(),events
assert any(e.get('status')=='final' for e in events),events
print('Voz después del tono:',[e['text'] for e in events if e.get('status')=='final'])
