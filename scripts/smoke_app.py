"""Real loopback HTTP/WebSocket smoke. Only synthetic content, guest session."""
import asyncio
import io
import json
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
import httpx
import numpy as np
import websockets
ROOT=Path(__file__).resolve().parent.parent
BASE='http://127.0.0.1:8765'
client=httpx.Client(base_url=BASE,trust_env=False,timeout=15)
token=client.get('/api/bootstrap').json()['token']
client.headers['X-Local-Token']=token
r=client.post('/api/sessions',json={'mode':'Tutor'});r.raise_for_status();sid=r.json()['id']
p=subprocess.run([sys.executable,'-m','assistant.tts_worker'],input=json.dumps({'text':'Mañana entrego los ejercicios de cálculo. No, el viernes.'}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
assert p.returncode==0
with wave.open(io.BytesIO(p.stdout)) as w:
    rate=w.getframerate()
    raw=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
samples=np.interp(np.arange(int(len(raw)*16000/rate))*rate/16000,np.arange(len(raw)),raw).astype(np.float32)
raw.fill(0);del raw,p
samples=np.concatenate([samples,np.zeros(16000,dtype=np.float32)])

async def voice():
    events=[]
    cookie='; '.join(k+'='+v for k,v in client.cookies.items())
    async with websockets.connect(f'ws://127.0.0.1:8765/api/audio/{sid}?token={token}&speakers=true',origin=BASE,additional_headers={'Cookie':cookie}) as ws:
        async def receive():
            try:
                async for message in ws:
                    events.append(json.loads(message))
            except websockets.ConnectionClosed:
                pass
        receiver=asyncio.create_task(receive())
        for i in range(0,len(samples),3200):
            await ws.send(samples[i:i+3200].tobytes())
            await asyncio.sleep(0.2)
        await asyncio.sleep(1)
        response=await asyncio.to_thread(client.post,f'/api/sessions/{sid}/pause',json={})
        assert response.status_code==200
        await asyncio.wait_for(receiver,5)
    assert any(e.get('status')=='provisional' for e in events), events
    assert any(e.get('status')=='final' for e in events), events
    assert not any(e.get('error') for e in events), events
    print('WebSocket real:',len(events),'eventos; parcial/final y pausa correctos.')

asyncio.run(voice());samples.fill(0)
utterances=client.get(f'/api/sessions/{sid}').json()['utterances']
assert any('calculo' in u['text_literal'] or 'cálculo' in u['text_literal'] for u in utterances.values())
client.post(f'/api/sessions/{sid}/text',json={'text':'calcula (10-2)/4'}).raise_for_status()
for _ in range(20):
    s=client.get(f'/api/sessions/{sid}').json()
    if s['responses']: break
    time.sleep(0.1)
assert 'Resultado: 2.0' in s['responses'][-1]['text']
speech=client.post(f'/api/sessions/{sid}/speak',json={'response_id':s['responses'][-1]['id']})
speech.raise_for_status();assert speech.content.startswith(b'RIFF')
print('API de síntesis real:',len(speech.content),'bytes WAV en RAM.')
client.post(f'/api/sessions/{sid}/cancel',json={}).raise_for_status()
client.post(f'/api/sessions/{sid}/close',json={}).raise_for_status()
assert client.get(f'/api/sessions/{sid}').status_code==404
print('Cálculo, cancelación y cierre de sesión correctos; sin datos personales persistidos.')
