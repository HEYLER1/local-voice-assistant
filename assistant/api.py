import asyncio
import json
import os
import re
import secrets
import struct
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .storage import Store, now, uid
from .organizer import propose, fold
from .discourse import classify
from .live_questions import LiveQuestions
from .verification import calculate, evidence
from .engines import ConversationEngine, TelegramReader, ROOT, MODEL, terminate

DATA = Path(os.getenv('ASSISTANT_DATA_DIR', ROOT / '.local'))
store = Store(DATA)
engine = ConversationEngine()
live = LiveQuestions(engine)
telegram = TelegramReader()
clients = {}
sessions = {}
audio_jobs = {}
response_jobs = {}
voice_jobs = {}
voiceprint_versions = {}
embedding_jobs = {}
component_states = {}
PORT = int(os.getenv('ASSISTANT_PORT', '8765'))
ORIGINS = {f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'}
KINDS = {'courses', 'tasks', 'memories', 'documents'}


async def cancel(sid):
    s = sessions.get(sid)
    if s:
        s['generation'] += 1
        s['state'] = 'LISTENING' if sid in audio_jobs else 'PAUSED'
    if s:
        await live.invalidate(s,clear=False)
    await engine.cancel(sid)
    job = response_jobs.pop(sid, None)
    if job and job is not asyncio.current_task():
        job.cancel()
    voice = voice_jobs.pop(sid, None)
    if voice and voice.returncode is None:
        await terminate(voice)


async def stop_audio(sid):
    p = audio_jobs.pop(sid, None)
    if p and p.returncode is None:
        await terminate(p)


@asynccontextmanager
async def lifespan(app):
    yield
    for process in list(embedding_jobs.values()):
        if process.returncode is None:
            process.terminate()
            await process.wait()
    for sid in list(sessions):
        await stop_audio(sid)
        await cancel(sid)
    store.close()


app = FastAPI(lifespan=lifespan)


@app.middleware('http')
async def guard(request, call_next):
    if int(request.headers.get('content-length', '0')) > 600000:
        return JSONResponse({'detail': 'Entrada demasiado grande'}, status_code=413)
    if request.headers.get('host') not in {f'127.0.0.1:{PORT}', f'localhost:{PORT}', 'testserver'}:
        return JSONResponse({'detail': 'Host no autorizado'}, status_code=403)
    if request.headers.get('origin') and request.headers['origin'] not in ORIGINS:
        return JSONResponse({'detail': 'Origen no autorizado'}, status_code=403)
    if request.url.path.startswith('/api/') and request.url.path != '/api/bootstrap':
        token = request.cookies.get('local_session', '')
        if token not in clients or not secrets.compare_digest(request.headers.get('x-local-token', ''), clients[token]['csrf']):
            return JSONResponse({'detail': 'Abre el asistente local para autorizar esta sesión'}, status_code=401)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; img-src 'self' data:; frame-ancestors 'none'"
    response.headers['Permissions-Policy'] = 'microphone=(self), camera=(), geolocation=()'
    return response


@app.get('/')
async def index():
    return FileResponse(ROOT / 'ui' / 'index.html')


@app.get('/api/bootstrap')
async def bootstrap(request: Request):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Abre la aplicación directamente')
    key = request.cookies.get('local_session', '')
    if key not in clients:
        key = secrets.token_urlsafe(32)
        clients[key] = {'csrf': secrets.token_urlsafe(32), 'profile': None}
    response = JSONResponse({'token': clients[key]['csrf']})
    response.set_cookie('local_session', key, httponly=True, samesite='strict')
    return response


def client(request):
    return clients[request.cookies['local_session']]


def owner(request):
    p = client(request)['profile']
    if not p:
        raise HTTPException(403, 'Selecciona y confirma tu perfil local para acceder a datos personales')
    return p


def session(request, sid):
    s = sessions.get(sid)
    if not s or s['client'] != request.cookies.get('local_session'):
        raise HTTPException(404, 'Sesión no disponible')
    return s


class ProfileInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


@app.get('/api/profiles')
async def profiles():
    return [{**p, 'voiceprint': bool(store.list('voiceprints', p['id']))} for p in store.list('profiles', 'local')]


@app.post('/api/profiles')
async def create_profile(body: ProfileInput):
    return store.put('profiles', 'local', {'display_name': body.display_name.strip()})


class ProfileSelection(BaseModel):
    profile_id: str | None
    confirmed: bool


@app.post('/api/profile/select')
async def select_profile(request: Request, body: ProfileSelection):
    if body.profile_id and (not body.confirmed or not store.get('profiles', 'local', body.profile_id)):
        raise HTTPException(400, 'Confirma un perfil existente')
    for sid, s in list(sessions.items()):
        if s['client'] == request.cookies['local_session']:
            await stop_audio(sid)
            await cancel(sid)
            sessions.pop(sid, None)
    client(request)['profile'] = body.profile_id
    return {'profile_id': body.profile_id}


@app.get('/api/status')
async def status():
    asr = (ROOT / 'models' / 'asr.json').exists()
    llm = (MODEL / 'config.json').exists() and any(MODEL.glob('*.safetensors'))
    return {'components': {'transcription': {'state': component_states.get('transcription', 'descargado') if asr else 'no configurado', 'engine': 'Moonshine Small Streaming ES; se carga al iniciar'},
       'conversation': {'state': engine.state if llm else 'no configurado', 'engine': 'Qwen3-8B MLX 4 bits; proceso cancelable'},
       'memory': {'state': 'listo', 'engine': 'SQLite con contenido cifrado; selección explícita'},
       'voiceprint': {'state': 'experimental' if voiceprint_available() else 'no configurado', 'engine': 'Resemblyzer, requiere consentimiento; nunca autentica'},
       'diarization': {'state': 'experimental' if (ROOT / 'models/diarization.json').exists() else 'no configurado', 'engine': 'Moonshine/pyannote: etiquetas por ventana de 12 s; sin identificación personal automática'},
       'speech': {'state': 'descargado' if (ROOT / 'models/piper/es_ES-sharvard-medium.onnx').exists() else 'no configurado', 'engine': 'Piper español; audio en RAM, escucha pausada durante reproducción'},
       'telegram': {'state': 'configurado sin verificar' if telegram.url else 'no configurado', 'engine': 'Adaptador local de lectura'},
       'verification': {'state': 'listo', 'engine': 'Cálculo determinista y búsqueda textual en documentos autorizados'}},
       'privacy': 'Audio en memoria; no grabaciones de la aplicación. Swap y copias del sistema no auditados.', 'timezone': 'America/Lima'}


class SessionInput(BaseModel):
    mode: Literal['Escucha', 'Organización', 'Tutor'] = 'Organización'
    timezone: str = 'America/Lima'
    live_answers: bool = True


@app.post('/api/sessions')
async def create_session(request: Request, body: SessionInput):
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(400, 'Zona horaria no válida')
    for sid, s in list(sessions.items()):
        if s['client'] == request.cookies['local_session']:
            await stop_audio(sid)
            await cancel(sid)
            sessions.pop(sid, None)
    sid = uid()
    sessions[sid] = {'id': sid, 'client': request.cookies['local_session'], 'profile': client(request)['profile'],
                     'mode': body.mode, 'timezone': body.timezone, 'state': 'PAUSED', 'utterances': {},
                     'generation': 0, 'live_answers': body.live_answers, 'responses': [], 'proposals': {}, 'started_at': now()}
    return {'id': sid, 'state': 'PAUSED'}


@app.get('/api/sessions/{sid}')
async def session_state(request: Request, sid: str):
    s = session(request, sid)
    return {k: s[k] for k in ('id', 'mode', 'state', 'utterances', 'responses', 'proposals', 'live_answers')}


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    utterance_id: str | None = None
    revision: int | None = None
    speaker: str = Field(default='Perfil seleccionado', max_length=100)


def relevant_memories(text, items):
    words={w for w in re.findall(r'\w+', fold(text)) if len(w)>3}
    scored=[]
    for item in items:
        content=item.get('content') or item.get('title') or ''
        score=len(words & set(re.findall(r'\w+', fold(content))))
        if score or item.get('memory_kind') == 'preferencia':
            scored.append((score,item))
    return [item for score,item in sorted(scored,key=lambda pair:-pair[0])[:8]]


async def interpret(s, u, explicit=True):
    profile = s['profile']
    text = u['text_literal']
    courses = store.list('courses', profile) if profile else []
    proposal = propose(text, courses, u['at'], s['timezone'])
    s['proposals'].pop(u['id'], None)
    if proposal:
        proposal.update({'id': u['id'], 'revision': u['revision'], 'kind': 'tasks', 'source_utterance': u['id']})
        s['proposals'][u['id']] = proposal
    if fold(text).startswith('recuerda '):
        s['proposals'][u['id']] = {'id': u['id'], 'revision': u['revision'], 'kind': 'memories',
            'content': re.sub(r'^recuerda\s+(?:que\s+)?', '', text, flags=re.I), 'confirmation': 'confirmado',
            'scope': 'personal', 'memory_kind': 'episodio', 'valid_until': None,
            'source': {'text': text, 'at': u['at']}, 'source_utterance': u['id']}
    if not explicit:
        # Ambient questions get their own cancellable, public-only explanation path.
        # Non-question narration must not cancel an answer already in progress.
        return
    await cancel(s['id'])
    await live.invalidate(s,u['id'])
    generation = s['generation']
    s['state'] = 'INTERPRETING'
    async def respond():
        try:
            n = fold(text)
            docs = store.list('documents', profile) if profile else []
            sources = evidence(text, docs)
            memories = store.list('memories', profile) if profile else []
            memories = [m for m in memories if not m.get('valid_until') or m['valid_until'] >= datetime.now(ZoneInfo(s['timezone'])).date().isoformat()]
            tasks = store.list('tasks', profile) if profile else []
            verification_state = 'evidencia disponible, sin certificación automática' if sources else 'evidencia insuficiente'
            if n.startswith(('verifica ', 'comprueba ')):
                assertion = text.split(' ', 1)[1].strip()
                exact = [d for d in docs if fold(assertion) in fold(d['content'])]
                if exact:
                    response = 'Respaldado como cita textual en el material autorizado: ' + ', '.join(d['name'] for d in exact) + '. Esto acredita lo que dice la fuente; no certifica su veracidad externa.'
                    verification_state = 'respaldado como cita textual'
                else:
                    response = 'Evidencia insuficiente: no encontré esa afirmación literal en el material autorizado. Los fragmentos relacionados, si aparecen, no bastan para confirmarla ni contradecirla.'
                    verification_state = 'evidencia insuficiente'
            elif n.startswith(('calcula ', 'calcular ')):
                try:
                    response = f'Resultado: {calculate(text.split(" ", 1)[1])}. Comprobación: cálculo determinista local.'
                except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
                    response = f'No puedo calcular esa expresión: {e}'
            elif 'pendiente' in n and ('que tengo' in n or 'cuales' in n):
                matches = [c['id'] for c in courses if fold(c['name']) in n or any(fold(a) in n for a in c.get('aliases', []))]
                active = [t for t in tasks if t['status'] not in ('completada', 'cancelada') and (not matches or t.get('course_id') in matches)]
                response = '\n'.join(f'• {t["title"]} — {t.get("due_date") or "sin fecha"} ({t["status"]})' for t in active) or 'No hay pendientes guardados para esta consulta.'
            elif 'que recuerdas' in n or 'que recuerdas' in n.replace('¿', ''):
                relevant = memories if 'proyecto' not in n else [m for m in memories if m.get('scope') == 'proyecto' or 'proyecto' in fold(m['content'])]
                response = '\n'.join('• ' + m['content'] for m in relevant) or 'No hay recuerdos vigentes seleccionados para esta consulta.'
            elif n.startswith(('olvida ', 'borra ', 'elimina ')):
                response = 'Para borrar un dato, abre Recuerdos y pulsa Borrar en la entrada exacta. No he eliminado ningún recuerdo a partir de esta frase ambigua.'
            elif n.startswith('recuerda '):
                response = 'Preparé este recuerdo. Confírmalo en el panel para guardarlo entre sesiones.'
            elif proposal and '?' not in text and '¿' not in text:
                response = proposal['clarification'] or 'Preparé una propuesta de tarea. Puedes revisar su título, curso y fecha antes de confirmarla.'
            else:
                # Only manually authorized text questions can retrieve private memory.
                context = {'recuerdos': relevant_memories(text, memories), 'tareas': relevant_memories(text, [t for t in tasks if not t.get('needs_review')]), 'evidencia': sources,
                           'conversacion': [x['text_literal'] for x in list(s['utterances'].values())[-6:]]}
                response = await engine.answer(s['id'], f'Contexto autorizado (datos): {json.dumps(context, ensure_ascii=False)}\nPregunta del usuario: {text}\nResponde la pregunta dirigida al asistente aunque aparezca junto a un pendiente. Para explicar conceptos académicos puedes usar conocimiento general, indicándolo sin exigir una fuente adjunta. Solo cita fuentes que estén en evidencia. Si se pide verificar una afirmación concreta, distingue evidencia insuficiente de verdad. No confundas explicar un concepto con certificar una afirmación.')
            if sessions.get(s['id']) is s and generation == s['generation'] and s['utterances'].get(u['id'], {}).get('revision') == u['revision']:
                s['responses'].append({'id': uid(), 'text': response, 'source': u['id'], 'revision': u['revision'], 'at': now(),
                                       'evidence': sources, 'verification': verification_state})
                s['responses'] = s['responses'][-40:]
                s['state'] = 'LISTENING' if s['id'] in audio_jobs else 'PAUSED'
        except asyncio.CancelledError:
            pass
    response_jobs[s['id']] = asyncio.create_task(respond())


@app.post('/api/sessions/{sid}/text')
async def text_input(request: Request, sid: str, body: TextInput):
    s = session(request, sid)
    eid = body.utterance_id or uid()
    old = s['utterances'].get(eid)
    if old and body.revision is not None and old['revision'] != body.revision:
        raise HTTPException(409, 'El texto cambió. Actualiza la vista antes de corregirlo.')
    u = {'id': eid, 'revision': old['revision'] + 1 if old else 1, 'text_literal': body.text,
         'text_display': ' '.join(body.text.split()), 'status': 'corregido' if old else 'final',
         'speaker': ('Invitado · texto' if not s['profile'] and body.speaker == 'Perfil seleccionado' else body.speaker), 'at': old['at'] if old else now()}
    u['intents'] = classify(u['text_literal'])
    s['utterances'][eid] = u
    if len(s['utterances']) > 150:
        s['utterances'].pop(next(iter(s['utterances'])))
    s['responses'] = [r for r in s['responses'] if r['source'] != eid]
    if old and s['profile']:
        for kind in ('tasks', 'memories'):
            saved = store.get(kind, s['profile'], eid)
            if saved:
                saved['needs_review'] = True
                if kind == 'tasks':
                    saved['status'] = 'pendiente de aclaración'
                store.put(kind, s['profile'], saved)
    await interpret(s, u)
    return u


@app.get('/api/data/{kind}')
async def list_data(request: Request, kind: str):
    if kind not in KINDS:
        raise HTTPException(404)
    return store.list(kind, owner(request))


class EntityInput(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    title: str | None = Field(default=None, max_length=500)
    course_id: str | None = None
    due_date: date | None = None
    status: Literal['propuesta', 'pendiente de aclaración', 'confirmada', 'en curso', 'completada', 'cancelada'] = 'confirmada'
    content: str | None = Field(default=None, max_length=50000)
    scope: Literal['personal', 'proyecto', 'curso'] = 'personal'
    memory_kind: Literal['preferencia', 'episodio', 'decisión', 'contexto'] = 'episodio'
    valid_until: date | None = None
    source_id: str | None = None
    source_revision: int | None = None
    session_id: str | None = None
    supersedes_id: str | None = None


async def save_entity(request, kind, body, eid=None):
    if kind not in KINDS:
        raise HTTPException(404)
    profile = owner(request)
    data = body.model_dump(mode='json', exclude_unset=True)
    if eid:
        old = store.get(kind, profile, eid)
        if not old:
            raise HTTPException(404, 'No existe ese elemento')
        data = {**old, **data, 'id': eid}
    if body.source_id:
        if not body.session_id:
            raise HTTPException(400, 'Falta la sesión de procedencia')
        s = session(request, body.session_id)
        p = s['proposals'].get(body.source_id)
        if not p:
            previous = store.get(kind, profile, body.source_id)
            current = s['utterances'].get(body.source_id)
            if previous and current and previous.get('revision') == body.source_revision == current['revision']:
                return previous
        if not p or p['revision'] != body.source_revision or p['kind'] != kind:
            raise HTTPException(409, 'La propuesta cambió o dejó de ser válida')
        data = {**p, **data, 'id': p['id'], 'confirmation': 'confirmado', 'owner_id': profile}
        data.pop('clarification', None)
        data['needs_review'] = False
        data['was_uncertain'] = data.pop('uncertain', False)
        if kind == 'tasks' and body.status == 'confirmada':
            data['status'] = 'confirmada'
        s['proposals'].pop(body.source_id, None)
    if kind in ('courses', 'documents') and not data.get('name', '').strip():
        raise HTTPException(400, 'Escribe un nombre')
    if kind == 'tasks':
        if not data.get('title', '').strip():
            raise HTTPException(400, 'Escribe un título')
        if data.get('course_id') and not store.get('courses', profile, data['course_id']):
            raise HTTPException(400, 'Curso no autorizado')
        data['temporal_precision'] = 'date' if data.get('due_date') else 'unknown'
        data.setdefault('due_time', None)
    if kind in ('memories', 'documents') and not data.get('content', '').strip():
        raise HTTPException(400, 'Escribe el contenido')
    if kind == 'tasks':
        data.setdefault('status', 'confirmada')
    if kind == 'memories':
        data.setdefault('owner_id', profile)
        data.setdefault('scope', 'personal')
        data.setdefault('memory_kind', 'episodio')
        data.setdefault('valid_from', now())
        data.setdefault('retention', 'hasta borrar manualmente')
        data.setdefault('valid_until', None)
    data.setdefault('source', {'text': data.get('content') or data.get('title') or data.get('name'), 'at': now(), 'type': 'selección manual'})
    data['confirmation'] = 'confirmado'
    if body.supersedes_id:
        if kind != 'memories' or not store.get(kind, profile, body.supersedes_id):
            raise HTTPException(400, 'Recuerdo anterior no disponible')
        store.delete(kind, profile, body.supersedes_id)
    # Memory edits and deletions cancel outputs containing old content.
    for sid, s in list(sessions.items()):
        if s['profile'] == profile:
            await cancel(sid)
            s['responses'].clear()
    return store.put(kind, profile, data)


@app.post('/api/data/{kind}')
async def create_entity(request: Request, kind: str, body: EntityInput):
    return await save_entity(request, kind, body)


@app.put('/api/data/{kind}/{eid}')
async def update_entity(request: Request, kind: str, eid: str, body: EntityInput):
    return await save_entity(request, kind, body, eid)


@app.delete('/api/data/{kind}/{eid}')
async def delete_entity(request: Request, kind: str, eid: str):
    if kind not in KINDS:
        raise HTTPException(404)
    profile = owner(request)
    store.delete(kind, profile, eid)
    if kind == 'courses':
        for t in store.list('tasks', profile):
            if t.get('course_id') == eid:
                t['course_id'] = None
                store.put('tasks', profile, t)
    for sid, s in list(sessions.items()):
        if s['profile'] == profile:
            await cancel(sid)
            s['responses'].clear()
            # Purge ephemeral fragments so a forgotten entry cannot be regenerated.
            s['utterances'].clear()
            s['proposals'].clear()
    return {'deleted': True}


@app.post('/api/telegram/search')
async def telegram_search(request: Request, body: TextInput):
    owner(request)
    try:
        return await telegram.search(body.text)
    except Exception:
        raise HTTPException(503, 'Telegram no configurado o servicio de lectura no disponible')


def voiceprint_available():
    import importlib.util
    return importlib.util.find_spec('resemblyzer') is not None


@app.delete('/api/voiceprint')
async def revoke_voiceprint(request: Request):
    profile = owner(request)
    voiceprint_versions[profile] = voiceprint_versions.get(profile, 0) + 1
    job = embedding_jobs.pop(profile, None)
    if job and job.returncode is None:
        job.terminate()
        await job.wait()
    for entry in store.list('voiceprints', profile):
        store.delete('voiceprints', profile, entry['id'])
    return {'deleted': True}


async def embedding(request, profile):
    if not voiceprint_available():
        raise HTTPException(503, 'Motor de huellas no instalado')
    raw = await request.body()
    if len(raw) > 512000 or len(raw) < 192000 or len(raw) % 4:
        raise HTTPException(400, 'Se requieren entre tres y ocho segundos de audio mono a 16 kHz')
    if profile in embedding_jobs:
        raise HTTPException(409, 'Ya hay un registro de voz en curso')
    p = await asyncio.create_subprocess_exec(sys.executable, '-m', 'assistant.speaker_worker',
             stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
             env={**os.environ, 'NUMBA_CACHE_DIR': str(DATA / 'compiled-cache')})
    embedding_jobs[profile] = p
    try:
        output, _ = await asyncio.wait_for(p.communicate(raw), 45)
        del raw
        if p.returncode:
            raise HTTPException(400, 'No se pudo extraer la huella. Habla solo, sin ruido, durante ocho segundos.')
        return json.loads(output)
    except asyncio.TimeoutError:
        p.kill()
        await p.wait()
        raise HTTPException(503, 'El motor de huellas tardó demasiado')
    finally:
        embedding_jobs.pop(profile, None)


@app.post('/api/voiceprint/enroll')
async def enroll(request: Request):
    profile = owner(request)
    if request.headers.get('x-voice-consent') != 'true':
        raise HTTPException(403, 'Se requiere consentimiento explícito de la persona')
    revision = voiceprint_versions.get(profile, 0)
    fingerprint = await embedding(request, profile)
    if client(request)['profile'] != profile or revision != voiceprint_versions.get(profile, 0):
        raise HTTPException(409, 'Registro invalidado por cambio de perfil o revocación')
    for entry in store.list('voiceprints', profile):
        store.delete('voiceprints', profile, entry['id'])
    store.put('voiceprints', profile, {**fingerprint, 'profile_id': profile, 'consent_at': now()})
    return {'registered': True, 'quality': fingerprint['quality'], 'experimental': True}


@app.post('/api/voiceprint/compare')
async def compare(request: Request):
    # Compare only the explicitly selected profile. No search across unauthorized owners.
    profile = owner(request)
    fingerprints = store.list('voiceprints', profile)
    if not fingerprints:
        raise HTTPException(404, 'Este perfil no tiene huella')
    revision = voiceprint_versions.get(profile, 0)
    candidate = await embedding(request, profile)
    if client(request)['profile'] != profile or revision != voiceprint_versions.get(profile, 0):
        raise HTTPException(409, 'Comparación invalidada')
    if candidate['model_id'] != fingerprints[0]['model_id']:
        raise HTTPException(409, 'Modelo incompatible. Registra de nuevo la huella.')
    import numpy as np
    a, b = np.array(candidate['vector']), np.array(fingerprints[0]['vector'])
    similarity = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    return {'similarity': similarity, 'decision': 'sin decisión automática: umbral sin calibrar',
            'requires_manual_confirmation': True, 'access_granted': False}


@app.websocket('/api/audio/{sid}')
async def audio_socket(ws: WebSocket, sid: str):
    key = ws.cookies.get('local_session')
    s = sessions.get(sid)
    if ws.headers.get('origin') not in ORIGINS or not s or s['client'] != key or key not in clients or not secrets.compare_digest(ws.query_params.get('token', ''), clients[key]['csrf']):
        await ws.close(code=1008)
        return
    if sid in audio_jobs:
        await ws.close(code=1008)
        return
    await ws.accept()
    if not (ROOT / 'models' / 'asr.json').exists():
        await ws.send_json({'error': 'Transcripción local no instalada. Usa texto mientras configuras el motor.'})
        await ws.close()
        return
    await cancel(sid)
    p = await asyncio.create_subprocess_exec(sys.executable, '-m', 'assistant.asr_worker', *(['--speakers'] if ws.query_params.get('speakers') == 'true' else []), stdin=asyncio.subprocess.PIPE,
                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=65536)
    audio_jobs[sid] = p
    s['state'] = 'LISTENING'
    component_states['transcription'] = 'cargando'
    queue = asyncio.Queue(maxsize=8)
    epoch = uid()
    async def feed():
        while True:
            raw = await queue.get()
            p.stdin.write(struct.pack('<I', len(raw)) + raw)
            await p.stdin.drain()
            del raw
    async def receive():
        while True:
            packet = await ws.receive_bytes()
            if len(packet) > 32768 or len(packet) % 4:
                raise ValueError('Audio inválido')
            try:
                queue.put_nowait(packet)
            except asyncio.QueueFull:
                await ws.send_json({'error': 'El motor no sigue el ritmo. Se detuvo la escucha para evitar acumular audio.'})
                raise ValueError('Sobrecarga')
    async def output():
        while True:
            line = await p.stdout.readline()
            if not line:
                if s['state'] != 'PAUSED':
                    component_states['transcription'] = 'fallido'
                    await ws.send_json({'error': 'El motor de voz se detuvo; revisa Diagnóstico.'})
                break
            data = json.loads(line)
            if data.get('ready'):
                component_states['transcription'] = 'listo'
                await ws.send_json({'component_state':'listo'})
                continue
            eid = epoch + '-' + data['id']
            old = s['utterances'].get(eid)
            if old and old['status'] == 'corregido':
                continue
            u = {'id': eid, 'text_literal': data['text'], 'text_display': ' '.join(data['text'].split()),
                 'status': data['status'], 'revision': old['revision'] + 1 if old else 1,
                 'speaker': ('Perfil seleccionado' if s['profile'] and ws.query_params.get('personal') == 'true' and ws.query_params.get('speakers') != 'true' else data.get('speaker', 'Sin atribuir')), 'overlap': data.get('overlap', False), 'at': old['at'] if old else now()}
            u['intents'] = classify(u['text_literal'])
            s['utterances'][eid] = u
            if len(s['utterances']) > 150:
                s['utterances'].pop(next(iter(s['utterances'])))
            await ws.send_json(u)
            if u['status'] == 'final' and u['text_literal'].strip() and (not old or old['status'] != 'final' or old['text_literal'] != u['text_literal']):
                await interpret(s, u, explicit=False)
            live.observe(s,u)
    runners = [asyncio.create_task(fn()) for fn in (feed, receive, output)]
    try:
        await asyncio.wait(runners, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for runner in runners:
            runner.cancel()
        await asyncio.gather(*runners, return_exceptions=True)
        await stop_audio(sid)
        while not queue.empty():
            queue.get_nowait()
        s['state'] = 'PAUSED'
        s['utterances'] = {k: v for k, v in s['utterances'].items() if v['status'] != 'provisional'}
        try:
            await ws.close()
        except Exception:
            pass


class SpeechInput(BaseModel):
    response_id: str


@app.post('/api/sessions/{sid}/speak')
async def speak(request: Request, sid: str, body: SpeechInput):
    s = session(request, sid)
    response = next((r for r in s['responses'] if r['id'] == body.response_id), None)
    if not response:
        raise HTTPException(404, 'Respuesta invalidada')
    if not (ROOT / 'models/piper/es_ES-sharvard-medium.onnx').exists():
        raise HTTPException(503, 'Síntesis española local no instalada')
    await stop_audio(sid)
    await cancel(sid)
    generation = s['generation']
    s['state'] = 'RESPONDING'
    p = await asyncio.create_subprocess_exec(sys.executable, '-m', 'assistant.tts_worker',
         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    voice_jobs[sid] = p
    try:
        spoken_text = re.sub(r'[*#`$]', '', response['text'])
        output, _ = await asyncio.wait_for(p.communicate(json.dumps({'text': spoken_text}).encode()), 45)
        if generation != s['generation'] or p.returncode:
            raise HTTPException(409, 'Síntesis cancelada o invalidada')
        if len(output) > 8_100_000:
            raise HTTPException(503, 'Respuesta hablada demasiado larga')
        return Response(output, media_type='audio/wav')
    except asyncio.TimeoutError:
        if p.returncode is None:
            p.kill()
            await p.wait()
        raise HTTPException(503, 'Síntesis cancelada por tiempo máximo')
    finally:
        if p.returncode is None:
            p.terminate()
            await p.wait()
        if voice_jobs.get(sid) is p:
            voice_jobs.pop(sid, None)
        if generation == s['generation']:
            s['state'] = 'PAUSED'


@app.post('/api/sessions/{sid}/{action}')
async def session_action(request: Request, sid: str, action: str, body: dict = {}):
    s = session(request, sid)
    if action in ('pause', 'close', 'cancel'):
        await cancel(sid)
        if action != 'cancel':
            s['state'] = 'PAUSED'
            await stop_audio(sid)
            s['utterances'] = {k: u for k, u in s['utterances'].items() if u['status'] != 'provisional'}
        if action == 'close':
            sessions.pop(sid)
        return {'state': 'CLOSED' if action == 'close' else s['state']}
    if action == 'live-answers':
        s['live_answers'] = bool(body.get('enabled', False))
        if not s['live_answers']:
            await live.invalidate(s,clear=False)
        return {'live_answers':s['live_answers']}
    if action == 'mode' and body.get('mode') in ('Escucha', 'Organización', 'Tutor'):
        await cancel(sid)
        s['mode'] = body['mode']
        return {'mode': s['mode']}
    raise HTTPException(400, 'Acción no válida')


app.mount('/ui', StaticFiles(directory=ROOT / 'ui'), name='ui')
