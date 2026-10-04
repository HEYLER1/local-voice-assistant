import asyncio
from assistant.discourse import extract_questions
from assistant.live_questions import LiveQuestions


def test_embedded_and_unpunctuated_questions():
    text='Filmamos un eclipse desde el espacio. ¿Por qué el episodio norte? El sol se vuelve blanco. cómo es que todavía no sabemos qué causan esas escurridizas bandas'
    q=extract_questions(text)
    assert any('episodio norte' in item for item in q)
    assert any('escurridizas bandas' in item for item in q)
    assert len(q)==2


def test_narration_without_question():
    assert extract_questions('España está a punto de vivir un eclipse. Estamos filmando un video.')==[]


class FakeEngine:
    """Only state/cancellation tests use this fake, never claims of model quality."""
    def __init__(self):
        self.prompts=[]
    async def cancel(self,key):
        pass
    async def stream_answer(self,key,prompt):
        self.prompts.append(prompt)
        yield 'Explicación '
        await asyncio.sleep(.02)
        yield 'general.'


def session():
    return {'id':'session','responses':[],'utterances':{},'profile':'secret-profile','live_answers':True}


def utterance(text,eid='u',revision=1):
    return {'id':eid,'revision':revision,'text_literal':text,'status':'final','speaker':'Sin atribuir'}


def test_ambient_answer_streams_without_private_context_and_no_duplicate():
    async def run():
        engine=FakeEngine(); live=LiveQuestions(engine);s=session()
        u=utterance('Una narración. ¿Por qué ocurre un eclipse?')
        s['utterances'][u['id']]=u
        live.observe(s,u)
        await asyncio.sleep(.16)
        assert s['responses'][0]['text']=='Explicación '
        assert s['responses'][0]['status']=='generando'
        # Metadata updates must not restart generation.
        live.observe(s,{**u,'revision':2})
        await asyncio.sleep(.06)
        assert s['responses'][0]['text']=='Explicación general.'
        assert s['responses'][0]['status']=='lista'
        assert len(engine.prompts)==1
        assert 'secret-profile' not in engine.prompts[0]
        assert 'recuerdos' not in engine.prompts[0]
        # Non-question narration does not cancel a prior response.
        v=utterance('Seguimos grabando el video.','v')
        s['utterances']['v']=v
        live.observe(s,v)
        await asyncio.sleep(.02)
        assert len(s['responses'])==1
    asyncio.run(run())


def test_disabled_and_correction_invalidation():
    async def run():
        engine=FakeEngine();live=LiveQuestions(engine);s=session();s['live_answers']=False
        u=utterance('¿Por qué ocurre un eclipse?');s['utterances']['u']=u
        live.observe(s,u);await asyncio.sleep(.2)
        assert s['responses']==[]
        s['live_answers']=True;live.observe(s,u);await asyncio.sleep(.2)
        assert s['responses']
        corrected=utterance('Esto es una afirmación.','u',2);s['utterances']['u']=corrected
        live.observe(s,corrected);await asyncio.sleep(.02)
        assert s['responses']==[]
    asyncio.run(run())
