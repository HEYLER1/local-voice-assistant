from pathlib import Path
import json
from moonshine_voice.download import get_diarization_model
ROOT=Path(__file__).resolve().parent.parent
path=get_diarization_model(cache_root=ROOT/'models/moonshine')
(ROOT/'models/diarization.json').write_text(json.dumps({'path':path,'source':'Moonshine/pyannote community-1','experimental':True}))
print('Modelos de separación de hablantes descargados.')
