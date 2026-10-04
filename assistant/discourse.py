"""Conservative discourse cues, independent from the ASR's acoustic boundaries.
Labels describe an intervention; they never certify truth or authorize actions.
"""
import re
from .organizer import fold


def classify(text):
    n = fold(text).strip()
    if not n:
        return []
    quoted = bool(re.search(r'\b(dijo|pregunto|comento|segun)\b', n))
    labels = []
    if not quoted and ('?' in text or '¿' in text or re.search(r'^(como\b|que\b|cual\b|cuales\b|por que\b|cuando\b|donde\b|puedes\b)', n)):
        labels.append('Pregunta')
    if re.search(r'\b(no entiendo|no se si|tengo dudas?|me confunde|no estoy seguro|quiza|quizas|tal vez)\b', n):
        labels.append('Duda')
    if re.search(r'\b(no tiene sentido|por que deberia|cuestiono|no estoy de acuerdo|es realmente|como es posible)\b', n):
        labels.append('Cuestionamiento')
    if re.search(r'\b(entrego|entregar|tengo que|debo|pendiente|terminar|hacer la tarea)\b', n):
        labels.append('Posible tarea')
    if n.startswith('recuerda '):
        labels.append('Solicitud de recuerdo')
    if quoted:
        labels.append('Referencia a otra persona')
    return labels or ['Afirmación']


def extract_questions(text):
    """Locate questions inside narration; don't repair uncertain ASR words silently."""
    questions=[]
    for match in re.finditer(r'¿([^¿?]+)\?', text):
        question=match.group(1).strip()
        if len(question.split()) >= 3:
            questions.append('¿'+question+'?')
    # Unpunctuated ASR: only fairly specific interrogative cues, not every 'que'.
    pattern=r'\b(?:por\s+qu[eé]|c[oó]mo\s+(?:es\s+que|se|puede|puedo|funciona|ocurre)|qu[eé]\s+(?:causa|causan|significa|son|es)|cu[aá]l\s+(?:es|fue)|cu[aá]ndo\s+(?:ocurre|sera|será))\b'
    for match in re.finditer(pattern,text,re.I):
        end=re.search(r'[?.!¿]',text[match.start():])
        stop=match.start()+end.start() if end else len(text)
        phrase=text[match.start():stop].strip(' ,;')
        if len(phrase.split()) >= 4 and len(phrase) <= 500:
            question='¿'+phrase+'?'
            if not any(fold(phrase) in fold(q) for q in questions):
                questions.append(question)
    return questions[:4]
