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
p=subprocess.run([sys.executable,'-m','assistant.tts_worker'],input=json.dumps({'text':'¿Cómo ocurre un eclipse solar? Ahora seguimos mirando el cielo mientras llega la respuesta.'}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
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
        first=None;updates=0;last='';start=time.monotonic()
        for _ in range(240):
            state=await asyncio.to_thread(lambda:client.get(f'/api/sessions/{sid}').json())
            answers=[r for r in state['responses'] if r.get('live')]
            if answers:
                answer=answers[-1]
                if answer['text']!=last:
                    updates+=1;last=answer['text']
                    if first is None:first=time.monotonic()-start
                if answer['status']=='lista':break
            await asyncio.sleep(.5)
        assert answers and answer['status']=='lista',state
        print('Audio → pregunta → respuesta:',answer['questions'])
        print('Actualizaciones:',updates,'; primer texto tras envío:',round(first or 0,2),'s')
        print(answer['text'])
        response=await asyncio.to_thread(client.post,f'/api/sessions/{sid}/pause',json={})
        assert response.status_code==200
        await asyncio.wait_for(receiver,5)
    assert any(e.get('status')=='provisional' for e in events), events
    assert any(e.get('status')=='final' for e in events), events
    assert not any(e.get('error') for e in events), events
    print('WebSocket real:',len(events),'eventos; parcial/final y pausa correctos.')

asyncio.run(voice());samples.fill(0)
client.post(f'/api/sessions/{sid}/close',json={}).raise_for_status()
