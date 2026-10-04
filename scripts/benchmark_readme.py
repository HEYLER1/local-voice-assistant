"""Small reproducible synthetic benchmark. Audio only in RAM; no user data."""
import io,json,re,struct,subprocess,sys,time,unicodedata,wave,statistics
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
TEXTS=[
'Mañana entrego los ejercicios de cálculo. No, el viernes.',
'Un eclipse solar ocurre cuando la Luna se interpone entre la Tierra y el Sol.',
'El equipo decidió usar Python para organizar las tareas del proyecto.',
'La integración por partes permite transformar una integral en otra más sencilla.',
'¿Cómo se calcula el área de un círculo con un radio de cinco metros?'
]
def words(s):
    return re.findall(r'\w+', ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if not unicodedata.combining(c)))
def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]
rows=[]
for i,text in enumerate(TEXTS,1):
    p=subprocess.run([sys.executable,'-m','assistant.tts_worker'],input=json.dumps({'text':text}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,cwd=ROOT)
    assert p.returncode==0
    with wave.open(io.BytesIO(p.stdout)) as w:
        rate=w.getframerate();raw=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
    voice=np.interp(np.arange(int(len(raw)*16000/rate))*rate/16000,np.arange(len(raw)),raw).astype(np.float32)
    raw.fill(0);del raw,p
    for condition in ('Voz limpia','Voz + tonos'):
        audio=np.pad(voice,(0,max(0,195200-len(voice))))
        if condition!='Voz limpia':
            t=np.arange(len(voice))/16000
            tones=(np.sin(2*np.pi*220*t)+np.sin(2*np.pi*440*t)+np.sin(2*np.pi*660*t)).astype(np.float32)
            tones*=np.sqrt(np.mean(voice**2))/(np.sqrt(np.mean(tones**2))*10**(10/20)+1e-12)
            audio[:len(voice)]+=tones
        packets=b''.join(struct.pack('<I',len(c)*4)+c.tobytes() for c in [audio[j:j+3200] for j in range(0,len(audio),3200)])
        start=time.perf_counter()
        r=subprocess.run([sys.executable,'-m','assistant.asr_worker'],input=packets,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,cwd=ROOT)
        elapsed=time.perf_counter()-start
        assert r.returncode==0,r.stderr.decode()
        events=[json.loads(l) for l in r.stdout.splitlines()];last={}
        for e in events:
            if e.get('text'):last[e['id']]=e['text']
        hypothesis=' '.join(last.values());ref=words(text);err=distance(ref,words(hypothesis))
        row={'case':i,'condition':condition,'reference':text,'hypothesis':hypothesis,'words':len(ref),'word_errors':err,'wer':err/len(ref),'clip_seconds':len(audio)/16000,'asr_process_seconds':elapsed,'rtf':elapsed/(len(audio)/16000),'final_lines':sum(e.get('status')=='final' for e in events)}
        rows.append(row);print(i,condition,round(row['wer']*100,1),'% WER',flush=True)
    voice.fill(0)
result={'date':'2026-10-04','environment':'macOS, Apple Silicon, 16 GB RAM; Python 3.13; Moonshine Small Streaming ES; Piper es_ES-sharvard-medium','source':'Five authored synthetic Spanish sentences, synthesized locally; no personal recordings. Paired additive three-tone interference at 10 dB SNR, not real music.','normalization':'Lowercase, remove accents and punctuation; word-level Levenshtein (S+D+I)/N. Latest streamed text per utterance ID.','timing':'ASR process elapsed including model loading and 12.2 s padded clip processing, excluding TTS; audio submitted faster than real time. RTF is elapsed/clip duration, not live latency.','rows':rows}
(ROOT/'docs/assets/benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
