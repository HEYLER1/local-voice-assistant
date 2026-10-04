"""Run explicitly during setup. Application never downloads during a conversation."""
import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ['HF_HOME'] = str(ROOT / 'models' / '.hf')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
from huggingface_hub import snapshot_download, HfApi
from moonshine_voice.download import get_model_for_language, find_model_info
from moonshine_voice import ModelArch
path, arch = get_model_for_language('es', wanted_model_arch=ModelArch.SMALL_STREAMING, cache_root=ROOT / 'models' / 'moonshine')
(ROOT / 'models' / 'asr.json').write_text(json.dumps({'path': path, 'arch': int(arch), 'catalog': find_model_info('es', ModelArch.SMALL_STREAMING)}))
repo = 'Qwen/Qwen3-8B-MLX-4bit'
revision = '383413e909f3bc5303ce195ebbdf0339c5a1a2a3'
snapshot_download(repo, revision=revision, local_dir=ROOT / 'models' / 'conversation', allow_patterns=['*.json', '*.safetensors', '*.jinja', '*.txt', 'README.md', 'LICENSE'])
(ROOT / 'models' / 'conversation-source.json').write_text(json.dumps({'repo': repo, 'revision': revision}))
print('Modelos descargados. Ningún audio ni dato personal fue enviado.')
