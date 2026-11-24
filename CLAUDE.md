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
- Terreno: plugin Terrain3D (verificar compatibilidad con la versión de Godot y macOS antes de instalar). Alternativa: terreno como mallas por secciones.
- Carreteras: mallas generadas a partir de Path3D/Curve3D (o plugin de carreteras si es compatible).
- Vegetación: MultiMeshInstance3D con rangos de visibilidad.
- Audio: sonidos de Freesound.org; motor con varias capas según RPM (pitch y volumen).
- Control de versiones: Git + GitHub. Usar Git LFS para .glb, .png, .jpg, .exr, .hdr, .wav, .ogg.

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

## Estándar visual
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
