"""Local engines only. No network audio APIs and no fallback browser recognition."""
import asyncio
import json
import os
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'models' / 'conversation'


async def terminate(process):
    if process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), 1)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
    except ProcessLookupError:
        pass


class ConversationEngine:
    def __init__(self):
        self.jobs = {}
        self.state = 'descargado'
        self.lock = asyncio.Semaphore(1)

    async def answer(self, session_id, prompt):
        if not (MODEL / 'config.json').exists():
            return 'El modelo de conversación local aún no está instalado. Puedes organizar tareas, guardar recuerdos explícitos y hacer cálculos; las respuestas abiertas estarán disponibles después de instalar el modelo.'
        async with self.lock:
            import sys
            process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'assistant.llm_worker',
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            self.jobs[session_id] = process
            self.state = 'cargando'
            try:
                output, _ = await asyncio.wait_for(process.communicate(json.dumps({'prompt': prompt}).encode()), 120)
                if process.returncode:
                    self.state = 'fallido'
                    return 'El motor local no pudo responder. Revisa su estado en Diagnóstico.'
                self.state = 'listo'
                return output.decode().strip()
            except asyncio.TimeoutError:
                return 'El modelo tardó demasiado. Se canceló la respuesta.'
            finally:
                await terminate(process)
                if self.jobs.get(session_id) is process:
                    self.jobs.pop(session_id, None)

    async def stream_answer(self, job_id, prompt):
        if not (MODEL / 'config.json').exists():
            yield 'Modelo local de conversación no instalado.'
            return
        async with self.lock:
            import sys
            process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'assistant.llm_worker',
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            self.jobs[job_id] = process
            try:
                process.stdin.write(json.dumps({'prompt':prompt,'stream':True}).encode())
                await process.stdin.drain()
                process.stdin.close()
                async with asyncio.timeout(120):
                    while line := await process.stdout.readline():
                        yield json.loads(line)['delta']
                await process.wait()
                if process.returncode:
                    yield '\nEl motor local no pudo completar esta respuesta.'
            finally:
                await terminate(process)
                if self.jobs.get(job_id) is process:
                    self.jobs.pop(job_id,None)

    async def cancel(self, session_id):
        process = self.jobs.pop(session_id, None)
        if process:
            await terminate(process)


class TelegramReader:
    """Explicitly configured separate read-only service. Credentials never copied."""
    def __init__(self):
        self.url = os.getenv('ASSISTANT_TELEGRAM_URL', '')
        if self.url and not self.url.startswith(('http://127.0.0.1:', 'http://localhost:')):
            raise ValueError('Telegram requiere servicio en loopback')

    async def search(self, query):
        if not self.url:
            raise ValueError('Telegram no configurado. Conecta un servicio de lectura autorizado.')
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = await client.post(self.url + '/search', json={'query': query, 'limit': 10})
            response.raise_for_status()
            return response.json()
