import os
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.environ['HF_HOME']=str(ROOT/'models/.hf')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from huggingface_hub import hf_hub_download,HfApi
repo='rhasspy/piper-voices'
revision='c10ece1aade47bb51c153c893d14e5bf8e5b7117'
base='es/es_ES/sharvard/medium'
directory=ROOT/'models/piper'; directory.mkdir(exist_ok=True)
for name in ['es_ES-sharvard-medium.onnx','es_ES-sharvard-medium.onnx.json','MODEL_CARD']:
    path=hf_hub_download(repo,base+'/'+name,revision=revision)
    shutil.copyfile(path,directory/name)
(directory/'source.json').write_text(json.dumps({'repo':repo,'revision':revision,'source':base}))
print('Voz española descargada para síntesis en RAM.')
