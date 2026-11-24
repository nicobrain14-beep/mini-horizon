# Proyecto: juego de carreras de mundo abierto (estilo "mini Horizon") en Godot 4

## Visión
Juego de carreras en mundo abierto, con el look más realista posible para el hardware disponible, inspirado en el concepto de Forza Horizon (pero con identidad propia: nombres, carros y mapa originales).
- Manejo libre por un mapa abierto sin pantallas de carga.
- Carreras repartidas en el mapa: circuito, sprint, tierra.
- Zonas: pueblo pequeño, carretera de montaña, autopista, tramos de tierra, bosque.
- Ciclo día/noche (después) y clima (más adelante).
- Prioridad #1: que se vea y se sienta muy bien. Mejor poco contenido muy pulido que mucho contenido mediocre.
- Prioridad #2: que corra fluido en la Mac de desarrollo (ver "Hardware").

## Hardware de desarrollo (IMPORTANTE)
- MacBook con chip A18 Pro (GPU de 5 núcleos), 8 GB de memoria unificada, SSD de 256/512 GB, sin ventilador.
- Todo debe diseñarse pensando en este límite: memoria, número de objetos, sombras y efectos.
- Medir siempre el rendimiento antes y después de cambios grandes (monitor de Godot: FPS, memoria de video, draw calls).
- Si un efecto cuesta mucho, proponer una alternativa más barata que se vea parecida.

## Motor y herramientas
- Godot 4 (última versión estable), renderer Forward+. Si el rendimiento no alcanza, probar el renderer Mobile.
- Física 3D: Jolt (Project Settings → Physics → 3D → Physics Engine).
- Lenguaje: GDScript con tipado estático.
- Assets: Poly Haven (texturas PBR, HDRIs, modelos, CC0), modelos de carros genéricos (sin marcas), Blender para ajustes y exportar a glTF (.glb).
- Audio: sonidos de Freesound.org; motor con varias capas según RPM (pitch y volumen).
- Control de versiones: Git + GitHub. Usar Git LFS para .glb, .png, .jpg, .exr, .hdr, .wav, .ogg.

## Conexiones MCP de Claude Code
Usarlas siempre que estén disponibles, en lugar de pedirle al usuario que haga pasos a mano.
- Godot MCP (`claude mcp add godot -- npx @coding-solo/godot-mcp`; requiere Node.js):
  - Usarlo para abrir el editor, correr el juego y leer los errores/salida de depuración después de cada cambio.
  - Usarlo para crear escenas y agregar nodos cuando sea más seguro que editar `.tscn` a mano.
  - Si no está conectado, verificar errores con `godot --headless --path . --quit` y avisar al usuario.
- Blender MCP (`claude mcp add blender uvx mcp-for-blender`; requiere el complemento dentro de Blender abierto):
  - Usarlo para preparar modelos para Godot: separar llantas del chasis, poner el origen de cada llanta en su centro, aplicar escala (1 unidad = 1 m), orientar el carro hacia -Z, reducir polígonos si hace falta.
  - Crear piezas modulares sencillas (banquetas, barreras, señales, edificios simples) y exportar a `.glb` en `assets/models/`.
  - Puede descargar assets de Poly Haven directamente; guardar todo en las carpetas del proyecto.
- Solo usar los servidores MCP oficiales listados aquí. No instalar otros sin preguntar al usuario.

## Complementos de Godot
- Jolt (integrado): motor de física 3D. Project Settings → Physics → 3D → Physics Engine = Jolt.
- Terrain3D (AssetLib, de TokisanGames): terreno del mundo abierto. Usar su sistema de texturas (pintar asfalto/tierra/pasto/roca) y su sistema de instancias para pasto y rocas. Preparar texturas según su guía (albedo+altura y normal+rugosidad empacadas).
- Sky3D (AssetLib, de TokisanGames): ciclo día/noche, sol, luna, nubes. Controlar la hora del juego desde `GameManager`.
- Carreteras: usar un complemento de carreteras del AssetLib solo si es compatible con la versión de Godot del proyecto; si no, generar mallas de carretera desde Path3D/Curve3D con un script `@tool` propio.
- Vegetación extra: MultiMeshInstance3D con rangos de visibilidad y shader de viento.
- Antes de instalar cualquier complemento nuevo: verificar compatibilidad con la versión de Godot y macOS, y preguntar al usuario.

## Fuentes de assets
- Poly Haven (CC0): texturas PBR, HDRIs, modelos.
- ambientCG (CC0): texturas extra (asfalto mojado, concreto, banquetas).
- Kenney.nl y Quaternius (CC0): edificios y props sencillos para relleno lejano.
- Sketchfab: solo modelos con licencia que permita uso en juegos (CC0 / CC-BY, dar crédito). Sin marcas reales.
- Freesound.org: sonidos (revisar licencia de cada uno).
- Registrar cada asset con licencia que pida crédito en `CREDITS.md`.

## Skills del proyecto (`.claude/skills/`)
Usarlas cuando apliquen (licencias en `.claude/third_party_licenses/`):
- `racing-feel`: checklist de sensación de carreras (drift fácil, frenar para girar, giro suficiente, velocidad que se siente, tono de motor, reinicio rápido).
- `feel-pass`, `game-qa`, `game-ux-review`: revisar sensación, bugs y HUD con una build jugable.
- `systematic-debugging`, `verification-before-completion`, `writing-plans`: depurar con método, verificar antes de decir "listo", planear antes de funciones grandes.
- Blender (vía Blender MCP en la Mac): `vehicle-artist`, `blender-godot-export`, `export-pipeline`, `lod-pipeline`, `uv-workflow`, `texture-workflow`.

## Reglas de código
- GDScript con tipado estático (`var speed: float = 0.0`, `func foo(x: int) -> void`).
- Valores ajustables (potencia, agarre, suspensión, tiempos) como `@export`, nunca "hardcodeados". Agruparlos con `@export_group`.
- Comunicación entre sistemas con señales. Singletons (Autoload) solo para sistemas globales: `GameManager`, `RaceManager`, `SaveManager`, `AudioManager`.
- Un script por responsabilidad. Nombres de archivos en `snake_case`, clases con `class_name` en `PascalCase`.
- Los archivos `.tscn` y `.tres` son texto: se pueden editar, pero con cuidado. Para escenas complejas, preferir construir nodos por código o explicar los pasos en el editor.
- Después de cada cambio: verificar errores con `godot --headless --path . --quit` (o equivalente) y explicar cómo probarlo en el editor y qué debería verse.
- Cambios pequeños y verificables. Antes de una función grande, proponer un plan y esperar aprobación.

## Física del carro
- Implementar un vehículo propio basado en raycasts (suspensión por rueda, fuerzas de agarre lateral y longitudinal) sobre un `RigidBody3D`, porque da más control del "feel" que `VehicleBody3D`. Empezar con `VehicleBody3D` solo si se necesita un prototipo rápido.
- Estilo de manejo: arcade con peso (tipo Horizon): derrapes controlables, buen agarre, ayudas opcionales (control de tracción, estabilidad).
- Parámetros editables: curva de torque, relaciones de caja, peso, centro de masa, rigidez y amortiguación de suspensión, agarre por superficie (asfalto, tierra, pasto, mojado).
- Superficies detectadas por grupo o metadata del collider para cambiar agarre, sonido y partículas.

## Estándar visual ("look Horizon")
- Look objetivo: atardecer dorado, colores vivos pero creíbles, carro brillante, sensación fuerte de velocidad.
- Sensación de velocidad: cámara de persecución que se aleja y abre el FOV al acelerar, ligero temblor, partículas de polvo/humo al derrapar, marcas de llantas.
- Vegetación con shader de viento (barato).
- Noche: faros con SpotLight3D, farolas con glow, ventanas iluminadas con emisión.
- HUD estilo Horizon: velocímetro, marcha, minimapa, notificaciones de carrera.
- WorldEnvironment:
  - Cielo: HDRI de Poly Haven (PanoramaSkyMaterial) para pruebas; `PhysicalSkyMaterial` + sol animado para día/noche.
  - Tonemap AgX o ACES (elegir el que se vea mejor), exposición controlada.
  - SSAO, SSR (reflejos en carro y asfalto mojado), Glow sutil, niebla (distancia + altura), niebla volumétrica solo si el rendimiento lo permite.
  - Iluminación global: SDFGI solo si alcanza el rendimiento; si no, iluminación ambiental del cielo + ReflectionProbes en zonas clave.
- DirectionalLight3D como sol, sombras con cascadas ajustadas (distancia razonable, no máxima).
- Materiales PBR con StandardMaterial3D u ORMMaterial3D:
  - El mapa ARM de Poly Haven = AO/Roughness/Metal → usar directamente en `ORMMaterial3D`.
  - Normales en formato OpenGL (`nor_gl`) — Godot usa la convención OpenGL. NO usar `nor_dx`.
  - Usar triplanar o escalas de UV correctas para que nada se vea estirado.
- Asfalto con variación (manchas, desgaste, marcas de llantas) usando decals o un shader con máscaras.
- Pintura de carro: shader con clearcoat, metallic y roughness bajos para reflejos bonitos.
- Escala real en todo (1 unidad = 1 metro).
- Texturas: 2K máximo (carro y asfalto principal); 1K en general; 512 a distancia. HDRI en 2K. Compresión VRAM activada con mipmaps.
- Post-efectos de cámara: FOV dinámico con la velocidad, ligero temblor, motion blur solo si es barato (shader propio o desactivado).

## Rendimiento (objetivo en esta Mac)
- Objetivo: 60 FPS en escenas de prueba, 30+ FPS estables en el mundo abierto.
- Usar escala de render 3D con FSR (Project Settings → Rendering → Scaling 3D) para ganar rendimiento.
- Rangos de visibilidad (visibility_range) en todo objeto del mundo; versiones simplificadas (LOD) para lo lejano.
- Occlusion culling en la zona urbana.
- Mundo dividido en secciones que se cargan/descargan según la posición del jugador (streaming manual con `ResourceLoader.load_threaded_request`).
- Vigilar memoria: presupuesto total del juego bajo ~3 GB.

## Plan por etapas (actualizar el estado aquí)
1. [ ] Carro + look: proyecto base, Jolt, carro con física propia, cámaras (persecución, cofre), escena de prueba con HDRI, asfalto de Poly Haven y post-procesado.
2. [ ] Mapa pequeño: terreno de ~1×1 km, una carretera desde Path3D, bosque con MultiMesh, rangos de visibilidad.
3. [ ] Primera carrera: checkpoints, cronómetro, inicio/fin, mejor tiempo guardado.
4. [ ] Zona urbana: pueblo con piezas modulares, farolas, occlusion culling.
5. [ ] Sistema de eventos: varias carreras en el mapa, minimapa, HUD (velocímetro, marcha, tiempo), menú de pausa.
6. [ ] Ampliar: streaming por secciones, más mapa, ciclo día/noche, sonido de motor por capas, más carros.
7. [ ] Avanzado: rivales IA (seguir la línea de carrera), tráfico simple, garage/colores, fantasma de mejor vuelta.

## Estructura de carpetas
- `scripts/` — código GDScript (subcarpetas: `vehicle/`, `race/`, `world/`, `ui/`, `autoload/`)
- `scenes/` — escenas `.tscn` (`vehicles/`, `world/`, `ui/`, `levels/`)
- `assets/textures/polyhaven/` — texturas importadas (una carpeta por material)
- `assets/hdri/` — cielos HDRI
- `assets/models/` — modelos `.glb` (`cars/`, `props/`, `buildings/`, `vegetation/`)
- `assets/materials/` — materiales `.tres`
- `assets/shaders/` — shaders (`.gdshader`)
- `assets/audio/` — sonidos
- `tools/` — scripts de herramientas de editor (`@tool`, EditorScript)

## Herramientas a crear
- EditorScript que importe una carpeta de Poly Haven (diffuse, nor_gl, arm) y genere automáticamente un `ORMMaterial3D` `.tres`.
- Herramienta para colocar vegetación sobre el terreno con reglas (pendiente, distancia a la carretera).

## Legal
- No usar marcas, logos ni modelos de carros reales sin licencia. Carros genéricos o diseños propios.
- Revisar la licencia de cada asset; Poly Haven es CC0.

## Lista completa de herramientas

### Programas instalados en la Mac
- Godot 4.7 (renderer Forward+)
- Node.js (para Godot MCP)
- Blender (para modelos 3D)
- Git + GitHub con Git LFS (respaldos)

### Conexiones MCP de Claude Code
- Godot MCP: claude mcp add godot -- npx @coding-solo/godot-mcp
- Blender MCP: claude mcp add blender uvx mcp-for-blender

### Complementos de Godot
- Jolt Physics (ya activado)
- Terrain3D (TokisanGames) – terreno y pasto
- Sky3D (TokisanGames) – día/noche, sol, nubes

### Fuentes de assets
- Poly Haven y ambientCG: texturas PBR (asfalto, tierra, pasto, roca, aplanado/stucco), HDRIs
- Sketchfab, CGTrader, TurboSquid: modelos de carros de alta calidad
- Kenney.nl y Quaternius: relleno lejano
- Freesound.org: sonidos de motor, llantas, viento, ciudad
- Registrar créditos en CREDITS.md

## Realismo del carro (prioridad alta)
- Modelo 3D de buena calidad (~100k–300k triángulos para el carro principal), llantas separadas.
- Shader de pintura con clearcoat y flakes metálicos.
- ReflectionProbe que siga al carro + SSR.
- Sombra de contacto debajo del carro (decal oscuro suave).
- Calaveras y faros con emisión; faros con SpotLight3D de noche.
- Desenfoque de llantas al girar rápido.
- Inclinación de la carrocería en curvas y al frenar/acelerar.
- Desenfoque de velocidad en el piso y bordes de pantalla.
- Modo Foto: pausa el juego y sube toda la calidad (sombras, reflejos, profundidad de campo) solo para capturas.
- Las marcas reales solo para pruebas personales; para publicar, carros genéricos.

## Casas estilo pueblo mexicano (etapa 4)
- Kit modular creado con Blender MCP: muros con aplanado, ventanas con herrería, puertas de madera, balcones, pretiles, tinacos, postes con cables, banquetas con guarnición amarilla.
- Un solo material de pared con parámetro de color (azul, rosa, amarillo, terracota, blanco) + máscaras de suciedad, humedad abajo, pintura descarapelada y escurrimientos.
- Herramienta @tool en Godot que genere calles automáticamente con casas de tamaños, colores y desgaste al azar.
- Detalles: macetas, letreros, cables entre postes, plantas.
- Rendimiento: piezas compartidas (instancias), rangos de visibilidad y versiones simples para casas lejanas.
