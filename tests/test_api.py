import asyncio
import pytest
from fastapi.testclient import TestClient
import assistant.api as api
from assistant.storage import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setattr(api, 'store', store)
    api.clients.clear()
    api.sessions.clear()
    with TestClient(api.app) as c:
        token = c.get('/api/bootstrap').json()['token']
        c.headers['X-Local-Token'] = token
        yield c


def profile(client, name='Yo'):
    p = client.post('/api/profiles', json={'display_name':name}).json()
    assert client.post('/api/profile/select', json={'profile_id':p['id'],'confirmed':True}).status_code == 200
    return p


def start(client):
    return client.post('/api/sessions', json={'mode':'Organización'}).json()['id']


def test_auth_origin_and_host(client):
    assert client.get('/api/status', headers={'X-Local-Token':''}).status_code == 401
    assert client.get('/api/status', headers={'Origin':'https://evil.test'}).status_code == 403
    assert client.get('/api/status', headers={'Host':'evil.test:8765'}).status_code == 403
    assert client.get('/api/bootstrap', headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403


def test_guest_cannot_retrieve_personal_data(client):
    assert client.get('/api/data/memories').status_code == 403
    assert client.post('/api/data/tasks',json={'title':'x'}).status_code == 403


def test_profiles_do_not_mix(client):
    a = profile(client,'Ana')
    client.post('/api/data/memories',json={'content':'Ana usa Python'})
    b = profile(client,'Luis')
    assert client.get('/api/data/memories').json()==[]
    client.post('/api/profile/select',json={'profile_id':a['id'],'confirmed':True})
    assert client.get('/api/data/memories').json()[0]['content']=='Ana usa Python'


def test_session_not_accessible_from_another_browser(client):
    sid=start(client)
    other = TestClient(api.app)
    tok=other.get('/api/bootstrap').json()['token']
    other.headers['X-Local-Token']=tok
    assert other.get('/api/sessions/'+sid).status_code==404


def test_corrected_proposal_old_revision_cannot_commit(client):
    profile(client)
    sid = start(client)
    u = client.post(f'/api/sessions/{sid}/text', json={'text':'Mañana entrego tarea de Cálculo'}).json()
    u2 = client.post(f'/api/sessions/{sid}/text', json={'text':'Entrego tarea de Cálculo el viernes','utterance_id':u['id'],'revision':u['revision']}).json()
    old={'title':'Tarea','source_id':u['id'],'source_revision':u['revision'],'session_id':sid}
    assert client.post('/api/data/tasks',json=old).status_code == 409
    old['source_revision']=u2['revision']
    assert client.post('/api/data/tasks',json=old).status_code == 200
    assert len(client.get('/api/data/tasks').json())==1


def test_stale_transcript_edit_conflicts(client):
    sid=start(client)
    u=client.post(f'/api/sessions/{sid}/text',json={'text':'Hola'}).json()
    assert client.post(f'/api/sessions/{sid}/text',json={'text':'Otro','utterance_id':u['id'],'revision':0}).status_code==409


def test_tasks_clear_date_update_and_complete(client):
    profile(client)
    t=client.post('/api/data/tasks',json={'title':'Ejercicios','due_date':'2026-10-09','status':'confirmada'}).json()
    r=client.put('/api/data/tasks/'+t['id'],json={'due_date':None,'status':'completada'})
    assert r.status_code==200
    assert r.json()['title']=='Ejercicios' and r.json()['due_date'] is None and r.json()['status']=='completada'


def test_invalid_dates_and_unauthorized_course(client):
    profile(client)
    assert client.post('/api/data/tasks',json={'title':'x','due_date':'2026-02-30'}).status_code==422
    assert client.post('/api/data/tasks',json={'title':'x','course_id':'other'}).status_code==400


def test_preference_replacement_and_forgetting_clears_context(client):
    profile(client)
    sid=start(client)
    old=client.post('/api/data/memories',json={'content':'Prefiero Java'}).json()
    updated=client.post('/api/data/memories',json={'content':'Prefiero Python','supersedes_id':old['id']}).json()
    memories=client.get('/api/data/memories').json()
    assert len(memories)==1 and memories[0]['content']=='Prefiero Python'
    client.post(f'/api/sessions/{sid}/text',json={'text':'recuerda que prefiero Python'})
    assert client.delete('/api/data/memories/'+updated['id']).status_code==200
    assert client.get('/api/data/memories').json()==[]
    s=client.get('/api/sessions/'+sid).json()
    assert s['utterances']=={} and s['proposals']=={} and s['responses']==[]


def test_profile_switch_closes_old_session(client):
    a=profile(client)
    sid=start(client)
    profile(client,'Otro')
    assert client.get('/api/sessions/'+sid).status_code==404


def test_voiceprint_consent_and_revocation(client):
    p=profile(client)
    assert client.post('/api/voiceprint/enroll',content=b'x'*192000).status_code==403
    api.store.put('voiceprints',p['id'],{'vector':[0,1], 'model_id':'synthetic-test'})
    assert client.delete('/api/voiceprint').status_code==200
    assert api.store.list('voiceprints',p['id'])==[]


def test_telegram_disconnected_is_honest(client, monkeypatch):
    profile(client)
    monkeypatch.setattr(api.telegram,'url','')
    assert client.post('/api/telegram/search',json={'text':'Cálculo'}).status_code==503


def test_close_discards_session(client):
    sid=start(client)
    client.post(f'/api/sessions/{sid}/text',json={'text':'calcula 2+3'})
    assert client.post(f'/api/sessions/{sid}/close',json={}).status_code==200
    assert client.get('/api/sessions/'+sid).status_code==404


def test_speak_invalidated_response_rejected(client):
    sid=start(client)
    assert client.post(f'/api/sessions/{sid}/speak',json={'response_id':'old'}).status_code==404


def test_confirm_retry_is_idempotent(client):
    profile(client)
    sid=start(client)
    u=client.post(f'/api/sessions/{sid}/text',json={'text':'Mañana entrego ejercicios'}).json()
    data={'title':'Ejercicios','status':'confirmada','source_id':u['id'],'source_revision':u['revision'],'session_id':sid}
    first=client.post('/api/data/tasks',json=data)
    again=client.post('/api/data/tasks',json=data)
    assert first.status_code==again.status_code==200
    assert first.json()['id']==again.json()['id']
    assert len(client.get('/api/data/tasks').json())==1


def test_correct_confirmed_task_requires_review(client):
    profile(client)
    sid=start(client)
    u=client.post(f'/api/sessions/{sid}/text',json={'text':'Mañana entrego ejercicios'}).json()
    data={'title':'Ejercicios','status':'confirmada','source_id':u['id'],'source_revision':u['revision'],'session_id':sid}
    first=client.post('/api/data/tasks',json=data).json()
    corrected=client.post(f'/api/sessions/{sid}/text',json={'text':'Entrego ejercicios el viernes','utterance_id':u['id'],'revision':u['revision']}).json()
    stored=client.get('/api/data/tasks').json()[0]
    assert stored['needs_review'] and stored['status']=='pendiente de aclaración'
    data['source_revision']=corrected['revision']
    second=client.post('/api/data/tasks',json=data).json()
    assert second['id']==first['id'] and not second['needs_review']
    assert len(client.get('/api/data/tasks').json())==1


def test_retrieval_is_relevant():
    items=[{'content':'Mi contraseña secreta no es contexto académico'}, {'content':'Proyecto usa Python'}, {'content':'Prefiero ejemplos cortos','memory_kind':'preferencia'}]
    selected=api.relevant_memories('Proyecto Python',items)
    assert len(selected)==2
    assert items[0] not in selected
