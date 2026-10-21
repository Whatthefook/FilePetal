# Changelog

## 1.11.0 — 2026-10-21

- Añade paquetes ZIP para Windows x64, Linux x64 y macOS Intel/Apple silicon.
- Añade una ventana pequeña y translúcida para soltar archivos en macOS y Linux;
  desde ella se abren las ruedas existentes de conversión, herramientas y acciones.
- Permite iniciar FilePetal con rutas de archivo para abrirlas en la rueda.
- Adapta la carpeta de datos, los iconos, los ajustes y la apertura de carpetas a
  macOS/Linux. La integración de Explorer y su acción Compartir siguen siendo
  específicas de Windows.
- FFmpeg/FFprobe y las utilidades RAR siguen siendo dependencias externas; las
  notas de descarga y compatibilidad describen esas limitaciones.

## 1.10.2 — 2026-10-09

- Corrige un estado residual de los nuevos controles numéricos: las flechas
  se actualizan aunque el editor bloquee señales al sincronizar dimensiones
  desde el lienzo. Después de arrastrar un recorte, vuelve a ser posible
  aumentar o reducir sus dimensiones con los botones.
- Añade regresiones para enteros y decimales y reproduce la secuencia real
  de recorte → actualizar campos → pulsar flecha en el smoke empaquetado.

## 1.10.1 — 2026-10-09

- **Annotate:** vuelve a mostrar la imagen; el grosor ya no oculta el método
  `QWidget.width()`. Herramientas, cursores y barra de color/grosor reorganizados.
- **Recorte:** ocho tiradores visibles, incluidos los centros de los bordes,
  cursores por dirección, margen de interacción y proporción conservada al
  arrastrar o escribir dimensiones.
- **Selección múltiple:** recorte, anotación y censura se editan por imagen;
  fondo aplica los mismos ajustes a todas las imágenes seleccionadas.
- **Opciones guardadas:** compresión de imagen/vídeo/audio, collage y fondo
  permiten activar «Usar estos ajustes la próxima vez sin preguntar».
  Desactivado inicialmente; se puede revertir en Ajustes → Opciones de herramientas.
- **Controles numéricos:** botones accesibles de tamaño amplio, sin solapamiento
  del texto, con estados de foco, límite y deshabilitado en ambas apariencias.
- **Editor PDF:** selección con Ctrl/Shift, movimiento de grupos y botones para
  añadir o quitar imágenes. Conserva todos los archivos al crear el PDF.
- El instalador verifica estos editores y salidas reales con `--smoke-editors`,
  además de las pruebas de WebEngine y PDF del ejecutable empaquetado.

## 1.10.0 — 2026-10-08

### Novedades
- **PDF de imágenes integrado:** editor con orden natural, recibido y manual,
  cuadrícula y nombres opcionales; accesible desde bandeja, ajustes y rueda.
- **Explorer:** submenú clásico nativo y accesos «Enviar a» para una o múltiples
  imágenes; la solicitud se entrega a la instancia abierta de Tangerine.
- El motor comparte los códecs y el progreso de Tangerine, muestra avance por
  imagen, permite cancelar y publica el PDF de forma atómica con reserva de
  nombre exclusiva. No sobrescribe originales ni archivos existentes.
- Migración con respaldo de los registros de la utilidad PDF separada.
- Reintento limitado ante WinError 5/32 al publicar el PDF; conserva cancelación,
  reserva exclusiva y el error original si falla la limpieza del temporal.

### Distribución
- Incluye las correcciones de Qt WebEngine preparadas para 1.9.2; esa versión
  no se publicó de manera independiente.
- Bridge nativo construido con CMake/MSVC o MinGW; instalador por usuario y
  reparación de accesos desde ajustes. Rutas de iconos corregidas en el bundle.
- CI ejecuta pruebas y verificaciones reales del WebEngine y del flujo PDF en
  el ejecutable congelado antes de publicar los artefactos.

## 1.9.2 — preparación del 2026-10-07, incluida en 1.10.0

### Correcciones
- **Qt WebEngine empaquetado en Windows.** En la aplicación congelada, Tangerine
  ahora fija el proceso auxiliar, los recursos, las traducciones y la ruta de
  búsqueda de DLL al bundle instalado. Así evita que Qt seleccione un
  `QtWebEngineProcess.exe` de otra instalación de Python.
- El build verifica que el helper, `Qt6WebEngineCore.dll`, el módulo WebEngine
  y sus recursos estén incluidos, y que helper y DLL tengan la misma versión.
- El release de Windows ejecuta una página HTML local en el ejecutable final
  como smoke test del proceso auxiliar.

## 1.9.1 — 2026-09-27

La rueda ya no aparece sobre videojuegos ni aplicaciones a pantalla completa:
el gesto de arrastre (Shift + ratón) también es un mando de juego y no hay
nada que soltar encima de una ventana que cubre el escritorio.

### Novedades
- **Ocultar la rueda en juegos y aplicaciones a pantalla completa** (Ajustes →
  General), activado por defecto; desactívalo si alguna aplicación concreta
  necesita la rueda.

### Correcciones
- **Puerta de contexto del primer plano.** Antes de mostrar la rueda (y con la
  rueda fija) se consulta el contexto: las superficies del shell (Explorador,
  escritorio, barra de tareas) y las ventanas propias nunca se bloquean; se
  bloquean las clases de motores conocidos (Unity, Unreal, SDL, GLFW, LWJGL,
  Valve, Riot, GameMaker, Prism3D…), los estados de `SHQueryUserNotificationState`
  1–4 (sesión bloqueada, escritorio ocupado o presentación, Direct3D exclusivo,
  modo presentación) y las ventanas que cubren su monitor sin estar simplemente
  maximizadas.
- **Ni demasiado estricta:** las ventanas maximizadas siguen permitidas —aunque
  ocupen toda el área de trabajo con la barra de tareas autooculta—, la
  tolerancia geométrica es del 1 % (~11 px en 1080p) y cualquier fallo de la
  sonda deja la rueda activa.
- La rueda se oculta sola si una aplicación a pantalla completa toma el primer
  plano mientras está visible o fija.

### Rendimiento
- **Arranque más ligero.** La detección de motores ya no importa la pila de
  documentos, OCR y visión solo para comprobarla (medido: ~2,4 s de espera en
  el hilo de la interfaz y ~90 MB de memoria residente): ahora se comprueba
  que estén instalados sin cargarlos, y se importan cuando una conversión o
  herramienta los usa de verdad.
- El registro dejó de anotar las líneas informativas de comtypes en cada
  lectura de la selección.

### Verificación
- Suite completa: **183 pruebas** (182 verdes, 1 omitida por diseño: el render
  real necesita pantalla), incluidas 14 pruebas nuevas de la puerta de contexto,
  2 de integración con el monitor y 2 de detección de motores sin importarlos.
- Perfilado (sonda de memoria, offscreen): el calentamiento del catálogo pasa de
  ~2,4 s y +93 MB a ~0,02 s y ~0 MB; la memoria tras el arranque baja de
  ~148 MB a ~56 MB.
- Comprobación empírica en Windows 11: una ventana maximizada no se bloquea
  (`QUNS=5`, `SW_SHOWMAXIMIZED`); una ventana sin bordes que cubre el monitor
  no reporta `QUNS` ocupado (5) y se detecta por geometría.

## 1.9.0 — 2026-09-21

Márgenes, papel, numeración y metadatos en todas las salidas PDF, y render por
HTML también para TXT, RTF, ODT y PPTX: cada conversión de documentos sale como
un documento de verdad, no como un volcado de texto.

### Novedades
- **Márgenes y papel de impresión.** Las conversiones a PDF se imprimen con un
  `QPageLayout` explícito (A4, 16 mm a los lados y 18 mm arriba/abajo) en lugar
  del layout por defecto (márgenes 0), que pegaba el texto al borde y cortaba
  los bloques de código. Aplica a DOCX, XLSX, CSV y Markdown, y también a las
  salidas jpg/png, que pasan por el mismo PDF intermedio.
- **Ajustes de impresión** (Ajustes → Formatos → **Documentos y PDF**): papel
  A4/Carta, márgenes normales (16/18 mm), compactos (10/12 mm) o amplios
  (25/20 mm) y numeración de páginas opcional; se aplican a todas las
  conversiones de documentos a PDF, JPG y PNG.
- **Numeración y metadatos:** cada PDF de varias páginas se sella con «1 / 3»
  al pie y lleva Título, Autor, Creador y Productor («Tangerine 1.9.0»).
- **Render HTML para TXT, RTF, ODT y PPTX:** el texto plano se compone con la
  tipografía del render fiel (ya no Courier de 54 pt), RTF y ODT salen como
  párrafos legibles y las presentaciones, como una página por diapositiva con
  su número.
- **CSS de impresión afinado:** títulos que no quedan cortados al pie, filas de
  tabla enteras, cabecera de tabla repetida en cada página, viudas y huérfanas
  controladas y salto de página antes de cada diapositiva.
- **`@media screen`:** el HTML exportado (md→html) se lee bien en pantalla
  —columna centrada de 46 rem, código con scroll horizontal y diapositivas con
  separador en vez de saltos de página.
- **Fallbacks alineados:** si QtWebEngine no está disponible, los escritores
  reportlab usan el mismo papel y márgenes del preset y también numeran y
  sellan metadatos.

### Correcciones
- Corregida la impresión a sangre del render fiel (1.8.0): el PDF ya no pega el
  texto al borde ni corta los bloques de código y las tablas.
- El render real se colgaba cuando se lanzaba desde el hilo de la interfaz; el
  renderer ahora detecta el hilo y ejecuta el trabajo directo con su propio
  bucle de eventos.

### Verificación
- Suite completa: **165 pruebas** (164 verdes, 1 omitida por diseño: el render
  real necesita pantalla).
- Render real comprobado con pypdfium2: A4 de 595 × 842 pt, tinta a 44 pt
  (16 mm) del borde, «2 / 2» al pie y metadatos «Tangerine 1.9.0» en un PDF de
  dos páginas generado desde un Markdown.

## 1.8.0 — 2026-09-18

Selección múltiple de verdad (tipos mixtos y lotes), rueda fija con atajo
configurable y cierres múltiples, render fiel de documentos a PDF, navegación
con la rueda del ratón y corrección del aviso de instancia duplicada.

### Novedades
- **Selección múltiple real:** con archivos de tipos distintos la rueda ofrece
  la unión de destinos de todas las familias (p. ej. JPG+PDF → PNG, DOCX, JPG,
  TXT… nueve opciones) y al aplicar una conversión solo se procesan los
  archivos compatibles (`catalog.conversion_paths`); las herramientas por lotes
  (comprimir, collage, merge, unir vídeo…) actúan sobre todos los archivos
  compatibles y filtran por familia al aplicarse (`catalog.tool_paths`).
- **Arrastre que no pierde archivos:** un snapshot de la selección del
  Explorador (COM, en segundo plano) hidrata la lista cuando Windows entrega
  un único archivo en el portapapeles del arrastre (p. ej. Shift+clic), y
  `dragEnter` fusiona el payload colapsado con los archivos ya conocidos.
- **Rueda fija (toggle):** `Ctrl+Shift+W` (configurable en Ajustes → Rueda)
  abre la rueda con la selección del Explorador y la mantiene abierta al
  soltar las teclas; pulsado durante un arrastre fija la rueda ya visible. Se
  cierra de cinco formas: segundo combo, clic en un pétalo (aplica y cierra),
  clic fuera de la rueda, Escape y auto-cierre tras 15 s sin uso. La rueda del
  ratón mueve el foco y el flujo clásico de mantener Shift no cambia.
- **Scroll sobre la rueda:** la rueda del ratón mueve el pétalo enfocado con
  envolvente.
- **Render fiel de documentos:** DOCX, XLSX, CSV y Markdown → PDF se dibujan
  con el motor HTML/CSS real (QtWebEngine `printToPdf`): encabezados, tablas,
  listas y bloques de código con estilo (Pygments), sin volcados de texto
  plano; si el motor no está disponible, se conserva el escritor anterior.
  Markdown → HTML también usa este render.

### Correcciones
- **Instancia duplicada:** el aviso de "ya en ejecución" usaba `showMessage`
  con la firma equivocada para PySide6 6.11 (el tercer argumento es el icono,
  no la duración) y el segundo lanzamiento terminaba en un diálogo de error;
  ahora pasa `QSystemTrayIcon.MessageIcon.Information` + 5000 ms.

### Verificación
- **155 pruebas** pytest (1 omitida por diseño: el render real necesita
  pantalla), con 29 nuevas: catálogo mixto (unión y lotes), snapshot/
  hidratación del Explorador, rueda fija (pin, atajo, timeout, clic fuera),
  clic/scroll/cierre de la rueda y builders de render (Markdown, DOCX, XLSX,
  CSV). Además, verificación en vivo: atajo (aparece, persiste al soltar, pin
  a mitad de arrastre, cierre por clic fuera y por timeout) y render fiel de
  un Markdown real a PDF comprobado con pypdfium2.

## 1.7.1 — 2026-09-17

Corrección del arrastre real desde el Explorador: la rueda ya no parpadea,
pierde sus pétalos ni queda como no-op silencioso a mitad del gesto en
Windows 11.

### Correcciones
- **Arrastre estable:** Windows 11 informa el botón izquierdo como suelto en
  muestras aisladas mientras dura el arrastre OLE; el monitor lo tomaba por
  un clic nuevo, ocultaba la rueda y la volvía a mostrar con los pétalos
  vacíos, de modo que soltar en ese instante no hacía nada. Ahora una
  liberación solo cuenta tras 4 muestras consecutivas "suelto" (~64 ms) y las
  muestras ambiguas no avanzan el gesto (`tangerine/monitor.py`).
- **Pétalos a salvo:** si la rueda se vuelve a mostrar durante el mismo gesto
  sin una carga legible (Windows no publica siempre el portapapeles del
  arrastre), conserva los pétalos que `dragEnter` ya rellenó y cancela la
  despedida en curso (`TangerineWheel.cancel_dismiss`) en vez de vaciarlos.
- **Lectura de la carga:** con el botón pulsado y el Explorador en primer
  plano, una lectura directa de `CF_HDROP` cubre los equipos donde el formato
  `InShellDragLoop` no se publica.

### Verificación
- **126 pruebas** pytest, con 6 nuevas de regresión: ráfagas "suelto" y
  liberación real del monitor, ventana ambigua sin avance, `dragEnter`→`drop`
  de la rueda (pétalos y acción) y cancelación de la despedida.

## 1.7.0 — 2026-09-17

Paridad visual con la app oficial: el HUD pasa a superficies translúcidas de
"material" y la rueda, la tarjeta de progreso y los editores se rediseñan;
además, formatos nuevos (AVIF, audio, vídeo y subtítulos), herramientas
ampliadas (pixelado, fondo completo, edición de foto, GPS) y navegación por
teclado.

### Interfaz
- **Superficies de material:** nuevo módulo `tangerine/hud.py` — captura del
  escritorio tras cada superficie (`QScreen.grabWindow`), desenfoque y lavado
  cálido; si la captura falla, queda solo el lavado. Aplicado a la rueda, la
  tarjeta de progreso y las ventanas de editor.
- **Rueda:** pétalos en cuña con esquinas redondeadas y halo; conversión = solo
  etiqueta grande en mayúsculas (sin iconos); herramientas = icono de línea
  monocromo + etiqueta; hover naranja ~120 ms con empuje; cápsula central que
  entra deslizándose con el nombre del elemento señalado; aparición escalonada
  (~254 ms) y despedida rápida (~160 ms); set de iconos vectoriales nuevo
  (`icons.py`), sin emoji.
- **Tarjeta de progreso:** chip de cierre melocotón, título en negrita,
  nombre del archivo y barra fina naranja.
- **Ventanas de editor:** cabecera propia (chip de cierre, título centrado y
  hairline), sliders naranja con thumb blanco, chips melocotón y botón
  **Apply** naranja.
- **Tema de apariencia:** **Ajustes → General → Apariencia** =
  Sistema/Claro/Oscuro (nuevo ajuste `appearanceTheme`, cambio en vivo).

### Formatos
- **Imagen:** AVIF como origen y destino (lectura y escritura con
  pillow-heif).
- **Audio:** OGG, Opus, AIFF y WMA como origen y destino (códecs vía FFmpeg).
- **Vídeo:** WebM, AVI y WMV como destino (VP9+Opus, MPEG-4+MP3, WMV2+WMAv2)
  y `.wmv` como origen.
- **Subtítulos:** familia nueva con SRT↔VTT y ambos →TXT; sin motor externo,
  decodificación tolerante (BOM/UTF-8/CP1252) y salida siempre UTF-8.

### Herramientas
- **Pixelado:** modo nuevo en Censurar foto y Censurar vídeo (mosaico de
  12 px), además de sólido y desenfoque.
- **Añadir fondo completo:** color, degradado con ángulo o imagen de fondo,
  con relación de aspecto, margen y radio de esquinas.
- **Editar foto completo:** exposición, contraste, saturación, temperatura,
  vibrance, nitidez, viñeta y grano, con presets Mono, Sepia, Noir, Vívido,
  Cálido y Frío.
- **Ubicación GPS:** el editor de metadatos de imagen muestra y permite
  editar latitud, longitud y altitud, y quitar la ubicación (solo imágenes).

### Interacción
- **Teclado con la rueda visible:** flechas para elegir (con vuelta circular),
  **Enter** aplica y **Escape** cancela.
- **Shift+Enter en el Explorador:** abre la rueda en el cursor con la
  selección actual, sin arrastrar (nuevo `tangerine/selection.py`, lectura por
  Shell.Application fuera del hilo de UI).
- **Modo táctil opcional:** mantener pulsado un arrastre ≥700 ms sin
  modificadores muestra la rueda (`touchLongPressEnabled`, desactivado por
  defecto).

### Correcciones
- Herramientas de imagen: corregidos los casos AVIF y BMP (metadatos, edición
  y guardado).
- La ubicación GPS se conserva al guardar metadatos de una imagen.

### Verificación (todo en verde)
- **120 pruebas** pytest, incluidos formatos v1.7.0, pixelado, fondo, edición
  de foto, GPS y teclado de la rueda.
- Auditoría de rutas: **43/43** identificadores de herramientas sin mensajes de
  "no disponible".
- Smoke de editores: **23/23** diálogos; regresión de copia: **11/11**;
  extremo a extremo: **50/50**; rutas de documentos: **38/38**.
- Compresión de PDF verificada: notes.pdf 1580 → 1154 B; PDF de 30 páginas
  27956 → 27408 B.

## 1.6.0 — 2026-09-16

Internacionalización (inglés/español), OCR opcional para PDF escaneados y una
ronda de correcciones, mejoras de memoria y empaquetado para la distribución.

### Idioma (i18n)
- Interfaz en **inglés** y **español**, con **431 claves por idioma**, en
  **Ajustes → General → Idioma**; la opción **Sistema** sigue el idioma de
  Windows (`es_MX` → español) y recurre al inglés si el locale no está
  soportado.
- El cambio se aplica al instante en la bandeja (menú y tooltip) y en la rueda;
  las ventanas de editor y de progreso ya abiertas lo aplican al volver a
  abrirse.
- Traducidos: rueda de conversiones y herramientas (pétalos incluidos), menú de
  bandeja, ajustes, los 20 diálogos de editor, ventanas de progreso y los
  errores comunes de motores/herramientas. Los nombres de archivo, códigos,
  rutas y demás datos no se traducen.
- Nuevo módulo `tangerine/i18n.py` (`tr()`, `set_language()`,
  `add_listener()`, resolución de `"system"` y cadena de reserva
  idioma → inglés → clave).
- Cobertura honesta: es una localización de interfaz; algunos mensajes de
  reserva poco frecuentes pueden seguir en inglés.

### OCR (PDF escaneados)
- Los PDF sin capa de texto se leen con **rapidocr-onnxruntime** (opcional,
  CPU, sin permisos de administrador) renderizando a 250 ppp.
  Instalación: `pip install -r requirements-ocr.txt`.
- Si el motor no está instalado, el error indica el comando exacto
  (`pip install rapidocr-onnxruntime`); docx→imagen sigue funcionando sin OCR.
- Con el motor instalado, el catálogo lo anuncia y las salidas txt/docx
  recuperan el texto de documentos escaneados.

### Corrección
- Memoria de los editores de foto: los lienzos de Recortar, Censurar y Anotar
  ya no conservan el mapa de bits a resolución completa; se muestra una copia
  reducida a la vez que el mapeo y la exportación siguen en píxeles reales.
- Recorte de imagen: la exportación vuelve a ser a resolución completa
  (regresión cubierta por pruebas de memoria y de recorte).

### Vídeo
- Visualizador de audio: el MP4 generado incluye la pista de audio y los
  vídeos sin audio fallan con un mensaje claro antes de invocar a FFmpeg.

### Empaquetado
- Flujo de empaquetado listo para Windows: `packaging\build.ps1` (PyInstaller
  onedir + ZIP portátil e instalador Inno Setup 6 cuando ISCC está presente),
  `packaging\tangerine.spec`, `packaging\installer.iss` y
  `packaging\version_info.txt`, además del flujo de compilación del instalador.

### Verificación (todo en verde)
- **85 pruebas** (77 existentes + 8 de i18n), incluida la paridad inglés/español
  (>150 claves), el formato con argumentos y la resolución `"system"` con
  locale no soportado.
- Auditoría de rutas: 43/43 identificadores de herramientas sin mensajes de
  "no disponible".
- Smoke de editores: 23/23 diálogos se construyen en modo offscreen, también
  con la interfaz en español.

## 1.5.0 — 2026-09-16

Nueva familia **Documentos** en la rueda de conversiones: ocho formatos (docx,
xlsx, pptx, csv, rtf, md, odt y epub) con sus rutas de salida, y la herramienta
**doc.compress** para recomprimir contenedores de Office.

### Documentos
- Conversiones: docx→txt/pdf/jpg/png; xlsx→csv/pdf/jpg/png;
  pptx→txt/pdf/jpg/png; csv→xlsx/pdf/jpg/png/txt; rtf→txt/pdf/jpg/png;
  md→txt/html/pdf/jpg/png; odt→txt/pdf/jpg/png; epub→txt.
- `doc.compress` (Alt+Shift): recomprime el ZIP interno de docx/xlsx/pptx a
  deflate máximo; si el resultado no es más pequeño, conserva el original.
- Dependencias nuevas: openpyxl, python-pptx, striprtf, odfpy y Markdown.

### Limitaciones honestas
- docx→pdf y pptx→pdf son a nivel de texto: estilos básicos y tablas como
  filas de texto; sin imágenes, formas, gráficos ni fidelidad de maquetación
  compleja.
- xlsx lee solo la hoja activa (valores en caché); doc→jpg/png se renderiza a
  través de un PDF intermedio a 300 ppp.
- Sin soporte de formatos binarios antiguos (.doc/.xls/.ppt): solo
  OOXML/ODF/texto (.docx/.xlsx/.pptx/.odt/.rtf/.md/.csv/.epub).

### Verificación (todos en verde)
- 33 pruebas de documentos: 31 rutas (origen → destino) ofrecidas por el
  catálogo y ejecutadas de extremo a extremo, `doc.compress` que nunca crece y
  error amigable ante un .docx corrupto. Suite completa: 60/60.

## 1.4.1 — 2026-09-16

Revisión de calidad y estabilidad ("code review hardening") aplicando las guías
addyosmani/agent-skills (code-review-and-quality) y awesome-skills
(code-review-skill): corrección, seguridad, arquitectura, rendimiento y
legibilidad. Todos los hallazgos bloqueantes e importantes fueron corregidos y
verificados.

### Seguridad
- Compresión de archivos: saneados los nombres de miembros que empiezan con
  `-`/`@` al crear RAR (evita inyección de argumentos en WinRAR).
- Extracción de `gz`: ahora por streaming (antes cargaba todo en RAM) con
  límite de tamaño; zip/tar con `filter="data"` y tope de 16 GB.
- Guardas para PDFs cifrados: mensaje claro "Password-protected PDFs are not
  supported" en lugar del confuso aviso de OCR.
- Ajuste de ventana (settings) con escritura atómica (`.json.tmp` + `os.replace`)
  y respaldo `.bak` si el JSON se corrompe; mutación bajo lock.

### Corrección
- EXIF: las imágenes rotadas (orientación 2-8) ya no se rotan dos veces al
  convertir JPEG/TIFF/WebP ni se exportan de lado a PDF/Word; los lienzos de
  Recortar/Censurar/Anotar y la detección de rostros trabajan en el espacio
  rotado correcto.
- Censurar video: las cajas inválidas ya no se ignoran en silencio; se avisa y
  se cancela con error si no queda ninguna válida (antes podía exportarse el
  video sin censurar).
- Fusionar PDFs ya no puede sobrescribir un "Merged PDF.pdf" anterior (colisión
  de nombres corregida).
- Conversiones fallidas o canceladas limpian archivos parciales (ffmpeg,
  archivos comprimidos) y ya no reportan éxito al cancelar.
- Dimensiones impares: se normalizan a pares en codificaciones x264 y en
  recortes de video (antes fallaba "width not divisible by 2").
- Velocidad de audio: guarda contra factor 0 (bucle infinito).
- Visualizador: las pistas de audio con audio de entrada ahora incluyen sonido.
- Metadatos: se conservan los metadatos EXIF de cámara completos (sub-IFD) al
  guardar copia, incluidos DateTimeOriginal, FNumber, ISO, LensModel.

### Estabilidad
- Cancelación real de trabajos (botón Cancel en la ventana de progreso) con
  limpieza de salidas y sin falsos "completado".
- Al salir con trabajos en curso se pide confirmación y se cancelan.
- Fin del bloqueo del hilo de UI por consultas al portapapeles/COM durante el
  arrastre; los análisis pesados (ondas de audio, fotogramas, caras) se
  difieren y muestran "Loading…".
- Miniaturas en collage para la vista previa (ya no reconstruye el collage
  completo en cada cambio).
- Ventanas de progreso ancladas (no pueden desaparecer por el recolector de
  basura) y no reaparecen si el usuario las cerró.
- Arranque único (lock) — una segunda instancia avisa y se cierra.
- Errores invisibles bajo `pythonw` ahora se registran en
  `%APPDATA%\Tangerine\crash.log` + `tangerine.log` (excepthook global).
- Ajustes de atajos del anillo: coincidencia por subconjunto (Shift+Ctrl ya no
  suprime la rueda), tecla Win derecha soportada, y el cambio de modo a mitad
  de arrastre reconstruye la rueda.

### Rendimiento
- Detección de motores memoizada y precalentada al inicio (antes ~550 ms en el
  primer arrastre).
- Copias de archivos sin recompresión con `copy2` (antes leían todo en RAM).
- `compress_image` reutiliza buffers y evita trabajo innecesario.
- Metadatos/ffprobe con menos bloqueos; cola de errores de ffmpeg para
  mensajes de fallo útiles.

### Verificación (todas en verde)
- 43/43 identificadores de herramientas enrutados (auditoría de rutas).
- 11/11 pruebas de regresión de arrastre (copiar, no mover).
- 50/50 pruebas extremo a extremo (conversiones + herramientas).
- Compresión de PDF: notes.pdf 1580 → 1154 B; PDF 30 páginas 27956 → 27408 B.

### Pendiente (roadmap)
- Dividir `editors.py` (2577 líneas) en paquete `editors/`.
- Reducir memoria de lienzos (pixmap de pantalla en lugar de resolución total).
- Unificar lógica duplicada de diálogos (ColorButton, run_and_close).
- Separar iconos y pintado de `wheel.py`.
- Visualizador para fuentes solo-video.
