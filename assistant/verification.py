import ast
import operator
import math
import re
from .organizer import fold

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
       ast.USub: operator.neg, ast.UAdd: operator.pos}


def calculate(expression):
    if len(expression) > 200:
        raise ValueError('Expresión demasiado larga')
    tree = ast.parse(expression.replace('^', '**'), mode='eval')
    if len(list(ast.walk(tree))) > 60:
        raise ValueError('Expresión demasiado compleja')
    def evaluate(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            if abs(n.value) > 1e12:
                raise ValueError('Número demasiado grande')
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = evaluate(n.left), evaluate(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 10 or abs(a) > 1e6):
                raise ValueError('Potencia fuera del límite')
            result = OPS[type(n.op)](a, b)
            if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError('Resultado fuera del límite')
            return result
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
            return OPS[type(n.op)](evaluate(n.operand))
        raise ValueError('Usa solo números y operaciones aritméticas')
    return evaluate(tree.body)


def evidence(query, documents):
    words = {w for w in re.findall(r'\w+', fold(query)) if len(w) > 3}
    result = []
    for doc in documents:
        for paragraph in doc['content'].split('\n'):
            score = len(words & set(re.findall(r'\w+', fold(paragraph))))
            if score:
                result.append({'source': doc['name'], 'excerpt': paragraph[:900], 'score': score, 'id': doc['id']})
    return sorted(result, key=lambda x: -x['score'])[:4]
