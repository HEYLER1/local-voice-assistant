import pytest
from assistant.discourse import classify


@pytest.mark.parametrize('text,label',[
    ('¿Cómo funciona la integración por partes?', 'Pregunta'),
    ('cómo funciona la integración por partes', 'Pregunta'),
    ('No entiendo este ejercicio', 'Duda'),
    ('No sé si eso es correcto', 'Duda'),
    ('No estoy de acuerdo con esa conclusión', 'Cuestionamiento'),
    ('Mañana entrego los ejercicios', 'Posible tarea'),
    ('Recuerda que prefiero ejemplos', 'Solicitud de recuerdo'),
    ('Los días del verano son largos', 'Afirmación'),
    ('Ana preguntó cómo funciona', 'Referencia a otra persona'),
])
def test_discourse(text,label):
    assert label in classify(text)


def test_quoted_question_is_not_an_order():
    assert 'Pregunta' not in classify('Ana preguntó: ¿cómo funciona?')


def test_question_and_task_can_coexist():
    labels=classify('Mañana entrego ejercicios. ¿Cómo integro esto?')
    assert 'Pregunta' in labels and 'Posible tarea' in labels
