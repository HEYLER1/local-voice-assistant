from datetime import datetime
import pytest
from assistant.organizer import propose, resolve_time
from assistant.storage import Store
from assistant.verification import calculate, evidence

STAMP = '2026-10-03T23:00:00-05:00'


def test_correction_date_one_task():
    p = propose('Mañana entrego los ejercicios de integrales de Cálculo… no, el viernes. ¿Cómo era la integración por partes?',
                [{'id': 'calculo', 'name': 'Cálculo', 'aliases': []}], STAMP, 'America/Lima')
    assert p['due_date'] == '2026-10-09'
    assert p['due_time'] is None
    assert p['course_id'] == 'calculo'
    assert 'integración por partes' not in p['title']
    assert p['clarification']


def test_relative_date_uses_intervention_zone():
    assert resolve_time('mañana', '2026-10-04T02:00:00+00:00', 'America/Lima')[0] == '2026-10-04'


def test_maybe_is_never_confirmed():
    p = propose('Quizá haya tarea mañana', [], STAMP, 'America/Lima')
    assert p['uncertain'] and p['confirmation'] == 'inferido'
    assert p['status'] == 'propuesta'


def test_ambiguous_course_requires_question():
    p = propose('Entrego tarea de ese curso mañana', [{'id': 'a', 'name': 'A'}, {'id': 'b', 'name': 'B'}], STAMP, 'America/Lima')
    assert p['course_id'] is None and p['clarification']


@pytest.mark.parametrize('text', ['¿Qué tengo pendiente de Cálculo?', 'Ana propuso Python', 'El equipo decidió Python'])
def test_no_false_task(text):
    assert propose(text, [], STAMP, 'America/Lima') is None


def test_encryption_isolation_persistence_and_forgetting(tmp_path):
    s = Store(tmp_path)
    m = s.put('memories', 'a', {'content': 'este proyecto no guarda grabaciones'})
    assert not s.list('memories', 'b')
    assert b'grabaciones' not in (tmp_path / 'assistant.sqlite').read_bytes()
    s.close()
    s = Store(tmp_path)
    assert s.get('memories', 'a', m['id'])['content'] == m['content']
    s.delete('memories', 'b', m['id'])
    assert s.list('memories', 'a')
    s.delete('memories', 'a', m['id'])
    s.close()
    s = Store(tmp_path)
    assert not s.list('memories', 'a')
    s.close()


def test_id_cannot_move_between_profiles(tmp_path):
    s = Store(tmp_path)
    m = s.put('tasks', 'a', {'title': 'entrega'})
    with pytest.raises(ValueError):
        s.put('tasks', 'b', m)
    s.close()


@pytest.mark.parametrize('expression,result', [('2+3*4',14), ('(10-2)/4',2), ('2^3',8), ('-3+2',-1)])
def test_calculations(expression,result):
    assert calculate(expression)==result


@pytest.mark.parametrize('expression', ['__import__("os").system("whoami")', '2**100000', '9**9**9', '[1,2]', '10/0'])
def test_reject_unsafe_calculation(expression):
    with pytest.raises((ValueError, ZeroDivisionError)):
        calculate(expression)


def test_documents_are_evidence_not_truth_certificates():
    sources = evidence('integración por partes', [{'id': 'x','name':'Apunte','content':'Integración por partes: integral u dv = uv - integral v du.'}])
    assert sources[0]['source']=='Apunte'
    assert sources[0]['id']=='x'
    assert evidence('entropía', [])==[]
