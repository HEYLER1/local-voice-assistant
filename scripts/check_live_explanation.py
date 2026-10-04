"""Real model test with the user's example, only ephemeral text in memory."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from assistant.engines import ConversationEngine
from assistant.live_questions import LiveQuestions

async def main():
    engine=ConversationEngine();live=LiveQuestions(engine)
    text=('Estamos con la NASA para filmar un eclipse desde el espacio. '
          'Todavía teníamos preguntas sin responder. ¿Por qué el episodio norte? '
          'El sol se vuelve blanco durante la totalidad. '
          'cómo es que todavía no sabemos qué causan esas escurridizas bandas')
    u={'id':'synthetic-text-example','revision':1,'text_literal':text,'status':'final','speaker':'Sin atribuir'}
    s={'id':'live-model-check','profile':None,'utterances':{u['id']:u},'responses':[],'live_answers':True}
    live.observe(s,u)
    start=asyncio.get_running_loop().time();first=None;changes=0;last=''
    while live.jobs:
        await asyncio.sleep(.1)
        if s['responses']:
            output=s['responses'][0]['text']
            if output!=last:
                changes+=1;last=output
                if first is None:first=asyncio.get_running_loop().time()-start
        if asyncio.get_running_loop().time()-start>125:
            await live.invalidate(s)
            raise RuntimeError('El modelo no terminó a tiempo')
    assert s['responses'] and s['responses'][0]['text']
    assert s['responses'][0]['status']=='lista'
    print('Preguntas:',s['responses'][0]['questions'])
    print('Actualizaciones visibles:',changes,'; primer texto tras',round(first or 0,2),'s')
    print('Respuesta real:',s['responses'][0]['text'])
asyncio.run(main())
