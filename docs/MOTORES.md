# Selección de motores y fuentes

Equipo inspeccionado: macOS 26.4, arm64, 16 GB, 10 núcleos. Python 3.13.15; se evitó 3.14 para las dependencias acústicas. Las versiones exactas se fijan en `requirements.lock`.

| Componente | Selección | Motivo y límite |
|---|---|---|
| Transcripción | moonshine-voice 0.1.5, Small Streaming ES, catálogo `quantized_26_08_24` | Streaming incremental real, CPU, español. Modelos descargados antes de conversar. Ventanas limitadas a 12 s. Sin WER medido con usuario. |
| Diarización | Moonshine/pyannote community-1 exportado a ORT | Dos archivos (~8 MB), API nativa disponible. Experimental por ventanas; no identidad estable. |
| Conversación | Qwen/Qwen3-8B-MLX-4bit, revisión `383413e909f3bc5303ce195ebbdf0339c5a1a2a3` | Tamaño elegido por preferencia de respuestas más completas y memoria disponible. ~4,1 GB. MLX permite GPU Apple; proceso aislado cancelable. No se afirma que sea el modelo más nuevo o mejor. |
| Huella | Resemblyzer 0.1.4, encoder distribuido con paquete | Extrae vector sin audio persistente. Alternativa pequeña a ECAPA y sus dependencias. Modelo entrenado principalmente con inglés; falta validar español y calibrar. Hash del peso en cada huella. |
| Síntesis | Piper 1.8.0, es_ES-sharvard-medium | API en RAM, voz española, tamaño pequeño. Modelo de dos voces; se usa la predeterminada, sin clonación. Escucha pausada durante salida. |
| Memoria | SQLite + Fernet | Sin servicio externo, contenido cifrado, borrado de filas y revisión controlada. Clave local con permisos restrictivos; llavero pendiente. |
| Interfaz | HTML/CSS/JS, markdown-it 15.0.2, KaTeX 0.19.0 | Se redujo el framework propuesto para no necesitar build ni Node al arrancar. Motores y API son reemplazables. HTML del modelo deshabilitado; fórmulas renderizadas localmente. |

Fuentes oficiales verificadas:

- [Moonshine](https://github.com/moonshine-ai/moonshine), [API de transcripción](https://moonshine-voice.readthedocs.io/en/latest/using/transcription/), [modelos disponibles y licencias](https://moonshine-voice.readthedocs.io/en/latest/models/available-models/).
- [Diarización y dependencias](https://github.com/moonshine-ai/moonshine/blob/main/docs/diarization-models.md).
- [Qwen MLX 8B](https://huggingface.co/Qwen/Qwen3-8B-MLX-4bit).
- [Resemblyzer y MIT](https://github.com/resemble-ai/Resemblyzer).
- [Piper y GPL-3.0](https://github.com/OHF-Voice/piper1-gpl), [ficha de la voz y atribución del dataset CC BY 3.0](https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_ES/sharvard/medium/MODEL_CARD).

Moonshine declara MIT para motores y modelos streaming actuales; sus modelos no streaming anteriores en idiomas distintos del inglés tienen licencia Community. La descarga instalada imprime todavía una advertencia genérica Community para cualquier idioma no inglés; se eligió explícitamente Small Streaming, no el modelo español Base antiguo. Esta diferencia entre documentación y mensaje se conserva como diagnóstico, sin afirmar licencia del modelo antiguo.

Las revisiones de Piper y modelos auxiliares están en sus manifiestos locales y se fijan también en los scripts de instalación. Las licencias de JavaScript se incluyen junto a los archivos en `ui/vendor`. Esta implementación no realiza redistribución comercial de pesos ni publicación remota.
