# Validación de esta implementación

Fecha de trabajo: 3 de octubre de 2026, America/Lima. Los ensayos finales pueden terminar después de medianoche.

## Evidencia obtenida

- 36 pruebas automatizadas: permisos, Host/Origin, aislamiento de perfiles y navegadores, revisiones, cambio de fecha, confirmación idempotente, corrección de tareas guardadas, fuente autorizada, cálculo limitado, persistencia/reinicio del almacén, borrado y limpieza de contexto, revocación de huellas y Telegram desconectado.
- Modelo real Qwen3-8B MLX 4 bits: pregunta de integración por partes enviada desde el navegador. Respondió con la fórmula y el ejemplo de integral de x·exp(x), sin fuentes inventadas. No es una evaluación de exactitud general ni una medición de latencia p95.
- Piper sintetizó «Mañana entrego los ejercicios de cálculo. No, el viernes.» en RAM.
- Moonshine Small Streaming ES emitió 7 actualizaciones parciales y una frase final: «mañana entrego los ejercicios de cálculo no el viernes».
- En una corrida, el procesamiento ASR de esa muestra sintética tomó aproximadamente 0,386 s. **No equivale a latencia del micrófono ni a una garantía de rendimiento.** El audio se suministró más rápido que tiempo real.
- Resemblyzer produjo un embedding real de 256 dimensiones, con 3,93 s de voz útil sintética. El umbral no está calibrado; no se midió identificación de humanos.
- El proceso ASR con diarización emitió 9 eventos y una etiqueta «Ventana 1 · Persona 1» para esa voz sintética. No valida separación de dos humanos.
- `pip check`: sin dependencias rotas. Python compilado y JavaScript comprobado sintácticamente.

## No probado todavía

Micrófono físico, permiso del navegador, acento del usuario, nombres propios, dos hablantes, falso reconocimiento, voces desconocidas, solapamiento, dispositivos distintos, pérdida de conexión prolongada, calidad de tutor en distintas materias, búsqueda Telegram real, respaldo del sistema y swap.

Las pruebas de permisos y datos usan casos sintéticos; las pruebas de motores ejecutan modelos reales con voz sintética local. No se guardaron grabaciones del usuario ni se accedió a su micrófono durante esta implementación.

## Primer ensayo del usuario

1. Crear perfil y curso Cálculo.
2. Iniciar escucha y decir la frase de mañana/viernes; revisar parciales y tarjeta final.
3. Pausar; comprobar el indicador global de micrófono apagado.
4. Corregir fecha; confirmar una sola tarea.
5. Guardar un recuerdo; cerrar aplicación y abrirla de nuevo; recuperar desde el perfil.
6. Borrar recuerdo y huella; comprobar que ya no aparecen.
7. Con consentimiento de otra persona, registrar su perfil y probar etiquetas por turnos. No interpretar semejanza como autorización.

## Integración real del servidor

`scripts/smoke_app.py` usó una sesión de invitado y contenido sintético por HTTP/WebSocket en loopback. Recibió 10 eventos con parcial/final y cierre al pausar; sin errores. El endpoint de síntesis devolvió 202.284 bytes de WAV en RAM para una respuesta de cálculo. Se verificaron cancelación y eliminación de la sesión al cerrar. No se crearon perfiles ni datos personales en esa prueba.

Durante la revisión del ejemplo que combina tarea y pregunta, el modelo inicialmente trató una explicación académica como una petición de certificación sin fuentes. Se corrigieron las instrucciones del coordinador para permitir conocimiento académico general, distinguirlo de verificaciones y seguir prohibiendo fuentes inventadas. La calidad lingüística aún requiere evaluación con más ejemplos.

La inspección de archivos encontró un archivo `.ses` de 51 bytes con una marca de tiempo y un identificador, sin audio ni texto conversacional. Se eliminó el artefacto de prueba y se excluyeron esos metadatos de Git. Esto no equivale a una auditoría de todas las escrituras del sistema operativo.

## Respuestas sobre preguntas incrustadas en audio

Se añadieron pruebas de extracción dentro de narración, preguntas sin signos, deduplicación ante revisiones de metadatos, salida progresiva, desactivación y eliminación de respuestas tras corregir el texto. Los ensayos de estados usan un motor ficticio explícito; no acreditan calidad del LLM. Total actual: 51 pruebas automatizadas.

`check_live_explanation.py` ejecuta el modelo real con un ejemplo textual de narración de eclipses y una pregunta incoherente. Este ensayo verifica generación progresiva, no calidad acústica ni veracidad científica de la respuesta. No lee datos de perfiles ni conserva la transcripción de ensayo.

`check_audio_questions.py` probó audio sintético en una sesión de invitado, con una pregunta seguida de narración. El servidor produjo 11 eventos de transcripción y una explicación progresiva completa; se observaron 6 actualizaciones y el primer texto apareció 8,15 segundos después de enviar el audio. La transcripción juntó pregunta y narración; el modelo explicó la interpretación clara y señaló la ambigüedad restante. Esta medición no garantiza latencia ni reconocimiento equivalentes con audio de videos reales. La sesión de ensayo se cerró sin guardar su texto.

## Resumen y selección de fragmentos en vivo

Total: 52 pruebas automatizadas. La nueva prueba comprueba que se agrupan revisiones, se conserva el texto que llega durante una generación, no se incluye el perfil privado y una corrección invalida el resumen previo. Se verificó también la interfaz con el modelo real y una narración de ejemplo sobre preparar un video de eclipses: aparecieron las tres secciones con salida completa. La selección de lo interesante sigue siendo una interpretación del modelo y puede repetir ideas; no es una comprobación de los hechos narrados. El resumen usa contexto acotado y un resumen anterior, por lo que una sesión larga puede perder detalles.

## Prioridad restaurada de preguntas

La extracción de preguntas conserva los mismos criterios de la versión anterior al resumen. Cuando llega una pregunta, se cancela la generación del resumen para liberar el modelo y se conserva el último resumen completo. El resumen vuelve a programarse tras las preguntas. Se añadieron pruebas de interrupción y conservación del resumen completo: total 53 pruebas aprobadas. No se ha medido nuevamente la latencia con audio real tras este ajuste.

## Selección estricta

55 pruebas aprobadas. Se comprueba que un fragmento nominal incoherente no invoca el modelo y que una decisión de descarte no crea respuestas. El ensayo real `check_question_selection.py` mezcló «¿Por qué el episodio norte?» con «¿Cómo ocurre un eclipse solar?»: solo la segunda recibió respuesta. Esta prueba no demuestra selección perfecta en todos los temas; el filtro es conservador y puede omitir preguntas válidas.

## Restauración solicitada

Se restauró la versión de preguntas en vivo anterior al resumen: 51 pruebas aprobadas, generación progresiva directa y procesamiento de transcripción parcial/final. Los apartados posteriores sobre resumen y selección estricta describen cambios históricos que ya no están activos. Los archivos retirados se conservaron en `.rollback-after-live-questions`.

## Compuerta de voz frente a sonidos

53 pruebas aprobadas, incluidas silencio, tonos de 440/1000 Hz y golpe aislado. El ensayo real `check_noise_filter.py` conservó el 100 % de la energía de una frase sintetizada, no produjo transcripción de un tono de 440 Hz sin voz y obtuvo una línea final de voz después del tono. Esto no acredita separación de música y diálogo ni rechazo de toda música instrumental. No se ha evaluado todavía el video concreto del usuario.

## Regresión reportada con video

El usuario reportó sustituciones y repeticiones graves con un video de YouTube. Se retiró de `asr_worker.py` la compuerta experimental y se restauró la entrada de audio sin sustitución por silencios. El funcionamiento de captura y transcripción con el video concreto no está validado; no se atribuye toda la regresión al filtro sin una comparación del mismo audio. Las 53 pruebas automatizadas incluyen dos del filtro aislado, que ya no está activo.

Se añadió entrada directa de audio de una pestaña mediante getDisplayMedia. Se verificaron sintaxis de JavaScript, 53 pruebas existentes y presencia del selector y sus instrucciones en la interfaz. No se autorizó ni ejecutó automáticamente el selector de compartición del navegador, y no se afirma validación acústica del video concreto con esta ruta.
