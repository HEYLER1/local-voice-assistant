"""Conservative extraction. Everything extracted is a proposal, never an obligation."""
import re
import unicodedata
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if not unicodedata.combining(c))


def resolve_time(text, timestamp, zone):
    local = datetime.fromisoformat(timestamp).astimezone(ZoneInfo(zone)).date()
    pattern = r'\b(?:hoy|manana|pasado manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|\d{4}-\d{2}-\d{2})\b'
    matches = list(re.finditer(pattern, fold(text)))
    if not matches:
        return None, None, None
    phrase = matches[-1].group()
    if phrase in ('hoy', 'manana', 'pasado manana'):
        result = local + timedelta(days={'hoy': 0, 'manana': 1, 'pasado manana': 2}[phrase])
    elif re.match(r'\d{4}-', phrase):
        try:
            result = date.fromisoformat(phrase)
        except ValueError:
            return None, phrase, 'La fecha no existe. Indica una fecha válida.'
    else:
        day = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'].index(phrase)
        result = local + timedelta(days=(day - local.weekday()) % 7)
        return result.isoformat(), phrase, f'¿Te refieres al {phrase} {result.isoformat()}?'
    return result.isoformat(), phrase, None


def propose(text, courses, timestamp, zone):
    literal = text.split('¿')[0].split('?')[0].strip(' .…')
    normalized = fold(literal)
    if not re.search(r'\b(entrego|entregar|entrega|tarea|ejercicios|pendiente|terminar|hacer|estudiar)\b', normalized):
        return None
    if re.search(r'\b(que tengo|cuales|consulta|lista)\b', normalized):
        return None
    candidates = [c for c in courses if any(re.search(r'(?<!\w)' + re.escape(fold(a)) + r'(?!\w)', normalized) for a in [c['name']] + c.get('aliases', []) if a.strip())]
    course = candidates[0] if len(candidates) == 1 else None
    due, phrase, clarification = resolve_time(literal, timestamp, zone)
    if len(candidates) > 1 or ('ese curso' in normalized and not course):
        clarification = '¿A qué curso corresponde este pendiente?'
    uncertain = bool(re.search(r'\b(quiza|quizas|tal vez|podria|posible)\b', normalized))
    return dict(title=literal[:500], course_id=course['id'] if course else None,
                due_date=due, due_time=None, temporal_precision='date' if due else 'unknown',
                original_time_phrase=phrase, status='pendiente de aclaración' if clarification else 'propuesta',
                confirmation='inferido', uncertain=uncertain, clarification=clarification,
                assignee=None, source={'text': literal, 'at': timestamp})
