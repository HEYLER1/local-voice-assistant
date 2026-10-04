# V — Asistente local en español

Asistente de voz local en español para macOS con Apple Silicon. Conversación con un modelo real, transcripción progresiva local, organización y memoria seleccionada. No es una demostración con respuestas simuladas. **La aceptación completa de voz con el usuario y dos personas todavía está pendiente.**

## Abrir en este Mac

1. Abre `run.command` con doble clic, o ejecuta `./run.command` desde esta carpeta.
2. Visita **http://127.0.0.1:8765**. La ventana de arranque debe permanecer abierta.
3. En **Perfiles y voz**, crea tu perfil. Seleccionarlo confirma que autorizas su memoria en esta sesión local. Usa Invitado si no quieres acceder a datos personales.
4. Puedes escribir preguntas inmediatamente. El micrófono empieza apagado.
5. Pulsa **Iniciar escucha** y concede permiso al micrófono únicamente en esa página local. Chrome/Edge o el navegador integrado requieren captura mono a 16 kHz. Si el navegador no la admite, la aplicación lo indica y permite seguir con texto.
6. **Pausar escucha** detiene captura y descarta el proceso de audio. **Detener** cancela generación y reproducción. **Cerrar sesión** descarta la transcripción temporal.

Para conversación hablada personal, marca **Solo hablo yo (perfil seleccionado)**. Es tu declaración explícita de quién interviene, no una identificación biométrica. Si hay más personas, desmárcalo. **Etiquetar voces** es una opción experimental separada; las etiquetas nunca autorizan acceso a recuerdos personales.

El instalador descarga los modelos en la carpeta local `models/` (no se incluyen en GitHub): Qwen3-8B MLX de 4 bits (~4,1 GB), Moonshine Small Streaming español (~126 MB incluidos modelos de hablantes) y Piper español (~73 MB). No hacen falta API keys, Ollama ni servicios de audio externos. Se usa la GPU Metal para conversación y CPU para voz. Python 3.13 está aislado en `.venv`.

## Recorrido de uso

- Añade **Cálculo** en Cursos y proyectos, con alias si corresponde.
- Escribe «Mañana entrego los ejercicios de integrales de Cálculo… no, el viernes. ¿Cómo era la integración por partes?».
- La tarea aparece **Por revisar**, con una fecha propuesta y una pregunta para confirmar el viernes. La pregunta académica se responde por separado. Revisa fecha, curso y título antes de guardar. No se inventa una hora.
- Para corregir una intervención, activa **Etiquetar voces** y usa **Editar texto o hablante**. Las propuestas viejas dejan de ser válidas. Si ya habías guardado una tarea, queda pendiente de revisión; reconfirmar actualiza el mismo ID.
- «¿Qué tengo pendiente de Cálculo?» consulta tareas guardadas del perfil elegido.
- «Recuerda que este proyecto no guarda grabaciones» prepara una tarjeta. **Revisar y confirmar** persiste solo ese texto y el fragmento mínimo de procedencia.
- Los recuerdos pueden editarse, tener caducidad o borrarse. Puedes guardar una preferencia nueva reemplazando otra mediante la API; en la interfaz, edita la existente.
- Pega apuntes en **Material de consulta**. Las respuestas pueden mostrar fragmentos de tus documentos autorizados. «Verifica [afirmación literal]» comprueba si esa cita está en tus documentos; no certifica la verdad externa de lo escrito.
- «Calcula (10 - 2) / 4» usa una herramienta aritmética determinista, sin ejecutar código libre.
- **Escuchar respuesta** genera voz con Piper en RAM. La escucha se pausa durante reproducción para evitar que la voz sintética se convierta en una nueva intervención. No se promete conversación full duplex ni AEC propio.

## Perfiles y huellas

Registro voluntario de ocho segundos, con consentimiento explícito antes del micrófono. Se procesa en un proceso desechable y se guarda solo el vector cifrado, modelo/versionado, calidad y fecha de consentimiento. **Borrar mi huella** revoca la referencia sin borrar el perfil. **Comparar con mi huella** muestra una similitud coseno experimental; no es un porcentaje de confianza ni otorga acceso.

La diarización usa modelos reales de Moonshine/pyannote. Las etiquetas se reinician por ventanas de 12 segundos y muestran su ventana para no confundirlas con identidades estables. No hay vinculación automática de una voz con recuerdos de otra sesión. Falta medir dos hablantes reales por turnos, desconocidos, ruido y solapamiento. La detección de solapamiento se limita a lo que devuelva el motor.

## Privacidad y almacenamiento

- Servidor en `127.0.0.1`, sin exposición automática por LAN. Cookie local HttpOnly/SameSite, token por navegador, comprobaciones de Host y Origin, y WebSocket autorizado por sesión.
- El acceso supone una sesión del sistema operativo confiable. Selección explícita de perfil, sin autenticación por voz ni contraseña independiente. Otro usuario con acceso al mismo escritorio puede seleccionar un perfil.
- SQLite guarda cargas cifradas con Fernet. La clave está en `.local/storage.key` con permisos 0600, separada del código; **todavía no usa el llavero del sistema**. Protege frente a lectura casual de la base, no frente a alguien que posea base y clave.
- No se guardan grabaciones ni historial completo. La aplicación no usa `SpeechRecognition` del navegador ni APIs remotas de audio. Modelos ya descargados funcionan offline; el launcher desactiva descargas/telemetría de Hugging Face y Piper desactiva eventos de telemetría de ONNX Runtime.
- Ventana ASR máxima de 12 s, cola del servidor de ocho paquetes (~1,6 s), un máximo de cuatro paquetes pendientes en el worklet (~0,8 s), cola de navegador limitada y parada ante sobrecarga. Al cerrar/pausar se termina el proceso de audio. La síntesis devuelve un WAV en RAM; nunca lo guarda en disco.
- Borrado físico de filas con `secure_delete` y compactación. No hay embeddings de recuerdos, índice semántico ni caché textual duradera. Borrar limpia el contexto efímero y cancela respuestas en vuelo para no recuperar el dato desde una sesión anterior.
- No se crean respaldos propios. Swap, crash dumps, APFS, Time Machine y copias realizadas por el sistema/usuario **no están auditados ni cubiertos por la garantía de borrado**.
- `.local`, `.venv`, modelos, audio y claves están excluidos de Git. No se creó repositorio remoto ni se copiaron credenciales del proyecto Telegram.

## Instalación reproducible

Esta versión está probada en macOS 26.4, Apple Silicon, 16 GB RAM, Python 3.13.15. El motor de conversación MLX requiere macOS/Metal; no se ofrece soporte probado para Windows o Linux.

En un Mac equivalente, abre `setup.command`. Instala las versiones de `requirements.lock` en `.venv` y descarga los pesos públicos. Solo la instalación necesita red. Las revisiones exactas están en `docs/MOTORES.md`; los scripts las fijan. Las librerías de formato de la interfaz están incluidas con sus licencias; Node no hace falta para ejecutar la aplicación.

Las descargas no requieren credenciales ni autorizan enviar conversaciones. Para un modelo distinto, realiza una decisión de compatibilidad explícita; no hay fallback externo automático.

## Telegram

**No configurado por defecto.** La aplicación continúa funcionando sin Telegram. Esta versión incluye un contrato de adaptador, no una conexión probada al servicio anterior. Requiere un servicio local autorizado que implemente:

`POST /search` con `{"query":"texto","limit":10}`, respuesta JSON con referencias/mensajes de lectura.

Configura `ASSISTANT_TELEGRAM_URL=http://127.0.0.1:PUERTO` al arrancar. Solo se admite loopback; no hay rutas de envío, borrado o modificación en esta aplicación. El conector anterior usa un protocolo distinto: deberá adaptarse y autorizarse antes de afirmar que la búsqueda está conectada. No se leen sus archivos de sesión ni secretos.

## Comprobaciones

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/test_local_engines.py
```

36 pruebas automatizadas del núcleo/API. La segunda prueba usa voz sintética de Piper, transcribe con Moonshine, extrae una huella real y ejecuta el adaptador de diarización. El audio solo existe en RAM. No mide precisión con el usuario. Resultados y limitaciones: `docs/VALIDACION.md`.

## Alcance pendiente

- Validación de micrófono y acento del usuario, WER, latencia p50/p95 de extremo a extremo y atribución de dos personas.
- Calibración de reconocimiento de hablantes entre sesiones; identificación continua y diarización estable de sesión completa.
- AEC con referencia sincronizada, full duplex y separación robusta de solapamientos.
- Extracción lingüística ampliada: el organizador actual es conservador y basado en reglas. No comprende cualquier anuncio o compromiso.
- Verificación semántica con clasificación de contradicción/evidencia mixta: hoy hay cita literal, fragmentos relacionados y cálculo.
- Integración efectiva con el protocolo del conector Telegram existente, si se autoriza.
- Cifrado de clave con llavero; configuración de dispositivo/intervenciones y ámbitos compartidos más completos.
- Caducidad automática de sesiones abandonadas cuando el navegador no puede enviar el cierre; los datos siguen siendo efímeros y se descartan al reiniciar.

No se presentan esas capacidades como implementadas o medidas. La base funcional permite trabajar por texto y voz local con las limitaciones visibles.

## Lectura por sentido

El texto en vivo agrupa afirmaciones consecutivas del mismo hablante en bloques y etiqueta preguntas, dudas, cuestionamientos, posibles tareas y solicitudes de recuerdo. Las revisiones técnicas se mantienen internamente, pero se ocultan en la vista principal. La edición de fragmentos está bajo «Editar texto o hablante».

La clasificación inicial usa señales lingüísticas conservadoras, no una comprensión semántica infalible. Las pausas del ASR siguen siendo límites acústicos internos; no determinan por sí solas los bloques mostrados. Las etiquetas no certifican afirmaciones ni confirman tareas. Esta actualización requiere reiniciar la aplicación para cargar el coordinador actualizado; reiniciar descarta el contexto temporal de la sesión actual.

## Preguntas del audio y respuestas al costado

«Responder preguntas del audio» activa explicaciones textuales de preguntas incrustadas en narraciones, incluidos videos y voces sin identificar. La respuesta aparece progresivamente en el panel de preguntas y respuestas; la captura sigue funcionando. Se pueden detectar preguntas tanto en hipótesis parciales como en finales, con una breve espera para evitar reaccionar a cada cambio de palabra.

Esta ruta solo usa conocimiento general y el contexto reciente del audio. No recibe recuerdos, documentos privados, tareas, perfiles ni herramientas; no ejecuta instrucciones del video y no habla automáticamente. Puede apagarse con el control visible. Una frase nueva sin pregunta no cancela la explicación de una pregunta anterior. Correcciones invalidan las respuestas derivadas de la pregunta modificada.

La detección todavía usa patrones lingüísticos: puede omitir preguntas sin signos o que quedan repartidas entre fragmentos, y confundir preguntas retóricas. Si la transcripción es incoherente, el modelo debe pedir reformulación en lugar de adivinar. Las respuestas generales no están verificadas mediante búsquedas externas. El tiempo hasta el primer texto depende de la carga del modelo y de la GPU; no se promete respuesta instantánea.


### Estado de la calidad de audio
El filtro experimental que sustituía tramos por silencio se retiró tras reportarse una regresión con video y música. La captura conserva la reducción de ruido del navegador. La precisión con el video del usuario sigue pendiente de evaluación; las pruebas sintéticas no acreditan esa calidad.

### Audio directo de un video
Para evitar escuchar el altavoz por el micrófono, abre el asistente y el video en Chrome, selecciona Fuente de audio → Audio del video (pestaña), pulsa Iniciar escucha y en el selector del navegador elige la pestaña del video con Compartir audio activado. La disponibilidad depende del navegador. Sin pista de audio, la captura se cancela con una indicación visible; no cambia silenciosamente al micrófono. La aplicación utiliza únicamente las pistas de audio y las mezcla a mono a 16 kHz; no procesa ni almacena imágenes. Pausar detiene todas las pistas compartidas. La calidad del video concreto queda pendiente de comparación con esta entrada.
