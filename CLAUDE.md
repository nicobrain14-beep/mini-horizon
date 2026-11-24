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
- CGTrader / TurboSquid: modelos de carros de pago de alta calidad (revisar licencia).
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
- Mixamo (mixamo.com, cuenta gratis de Adobe): personajes (NPCs) con animaciones (caminar, platicar, sentarse, saludar); libres de regalías
- Sketchfab también para edificios especiales (iglesia, kiosco, mercado); el resto del pueblo con el kit propio de Blender
- Freesound.org: sonidos de motor, llantas, viento, ciudad
- Registrar créditos en CREDITS.md

## Realismo del carro (prioridad alta)
- Modelo 3D de buena calidad (~100k–300k triángulos para el carro del jugador), llantas separadas, faros e interiores con detalle.
- Shader de pintura con clearcoat y flakes metálicos; parámetro de color para cambiar pintura.
- ReflectionProbe que siga al carro + SSR para reflejos del cielo y del entorno en la carrocería.
- Sombra de contacto debajo del carro (decal oscuro y suave) para que no se vea flotando.
- Calaveras y faros con emisión; de noche, faros con SpotLight3D.
- Desenfoque de llantas al girar rápido.
- Inclinación de la carrocería en curvas, frenadas y aceleraciones.
- Desenfoque de velocidad en el piso y bordes de pantalla.
- Modo Foto: pausa el juego, cámara libre, y sube toda la calidad (sombras, reflejos, profundidad de campo) solo para la captura.
- Marcas reales solo para pruebas personales; para publicar, carros genéricos.

## Casas estilo pueblo mexicano (etapa 4)
- Kit modular creado con Blender MCP: muros con aplanado, ventanas con herrería, puertas de madera, balcones, pretiles, tinacos, postes con cables, banquetas con guarnición amarilla, empedrado.
- Un solo material de pared con parámetro de color (azul, rosa, amarillo, terracota, blanco) + máscaras de suciedad, humedad abajo, pintura descarapelada y escurrimientos bajo ventanas.
- Herramienta @tool en Godot que genere calles automáticamente: casas de tamaños, colores y desgaste al azar.
- Detalles: macetas, letreros, cables entre postes, plantas, kiosco y plaza, iglesia, mercado.
- Rendimiento: piezas compartidas (instancias/MultiMesh), rangos de visibilidad y versiones simples para casas lejanas.

## Personas (NPCs)
- Personajes y animaciones de Mixamo, importados a Godot.
- Pocos a la vez: 10–20 cerca del jugador, solo en el pueblo; aparecen y desaparecen según la distancia (los personajes animados son caros en esta Mac).

## Mapa del mundo y mapa del juego (estilo Forza Horizon / GTA)

### Distribución del mundo (~2×2 km al inicio)
- Norte: Sierra (mirador, antena, curvas de montaña). Noreste: Barranca (camino junto al precipicio).
- Oeste: Bosque (rally entre pinos) y Río (brechas que lo cruzan).
- Centro: Pueblo mexicano (plaza con kiosco, mercado, iglesia, callejones) + Festival (base del jugador) al lado.
- Este: Autopista (rectas largas, radares de velocidad).
- Sur: Rancho y campos de magueyes (tierra y saltos). Suroeste: Lago (circuito).
- Todas las zonas conectadas por carreteras; atajos de tierra entre zonas.

### Mapa completo (pantalla de pausa, tecla M)
- Vista desde arriba del mundo entero, con zoom (rueda/gatillos) y arrastre.
- Imagen del mapa generada automáticamente con una herramienta @tool: cámara ortográfica desde arriba que "fotografía" el mundo y guarda una textura (estilizada: carreteras claras, agua azul, zonas con color suave). Regenerarla cuando cambie el mundo.
- Íconos por tipo de evento, con colores (y forma distinta, para no depender solo del color):
  - Azul – carreras de asfalto
  - Café/naranja – tierra y rally
  - Morado – contrarreloj y desafíos (radar, zona de velocidad, derrape, salto)
  - Amarillo/dorado – exhibiciones especiales
  - Verde – misiones de historia
  - Rosa – coleccionables y exploración (graneros, letreros, miradores)
  - Blanco – festival / casa del jugador
  - Gris – eventos bloqueados; palomita ✓ o estrellas en eventos completados
- Leyenda en una esquina y filtros para mostrar/ocultar cada tipo.
- Al pasar el cursor sobre un ícono: tarjeta con nombre, tipo, distancia, mejor tiempo y recompensa.
- Marcar destino (waypoint): clic en un ícono o en cualquier punto → se traza la ruta.
- Zonas descubiertas: las carreteras no visitadas se ven más oscuras hasta recorrerlas (niebla de mapa).
- Viaje rápido al festival y a eventos ya descubiertos (desbloqueable).

### Minimapa (HUD, esquina inferior izquierda)
- Circular, gira con el carro (el norte se mueve), muestra la misma textura del mapa.
- Muestra íconos cercanos con los mismos colores, flecha del jugador y la ruta GPS marcada en color sobre las carreteras.
- Íconos fuera de rango se quedan pegados al borde indicando la dirección.
- Durante una carrera: muestra los checkpoints y la línea de carrera.

### GPS y navegación
- Red de carreteras como grafo (nodos en intersecciones, generado desde los Path3D de carreteras) y ruta con A* (`AStar3D`).
- Línea de ruta en el minimapa y, opcional, flechas/brillo sobre el asfalto en el mundo.
- Recalcular la ruta si el jugador se desvía.

### Marcadores en el mundo
- Al acercarse a un evento: columna de luz del color de su tipo, visible a distancia, y círculo en el piso para iniciar.
- Notificación en pantalla al descubrir un evento nuevo ("Nuevo evento descubierto: Sprint de la Sierra").

### Implementación (orden)
1. `MapData` (Autoload): lista de eventos con posición, tipo, color, estado (bloqueado/disponible/completado).
2. Herramienta @tool que genera la textura del mapa desde arriba.
3. Minimapa en el HUD.
4. Mapa completo con zoom, leyenda, filtros y tarjetas.
5. Waypoints + GPS con A*.
6. Niebla de mapa y viaje rápido.

## Misiones y carreras (100 ideas)

### Sistemas necesarios (construirlos en este orden)
1. Checkpoints + cronómetro + inicio/fin (sirve para casi todas las carreras).
2. Radar de velocidad, zona de velocidad, zona de derrape, salto largo (retos de puntuación).
3. Fantasma de mejor vuelta y guardado de récords.
4. Eventos repartidos en el mapa (marcador, entrar y empezar) + condiciones (hora del día, clima).
5. Rivales IA siguiendo la línea de carrera.
6. Misiones con historia (objetivos, diálogos simples, entregas, pasajeros).
7. Modos especiales (policía, infectado, rey de la colina, etc.).

### Prioridad de implementación
- Etapa 3 (primeras): 1, 2, 23, 26, 27, 43.
- Etapa 4 (pueblo): 11, 33, 61, 62, 63, 65, 68.
- Etapa 5 (eventos en el mapa): 3, 4, 13, 18, 24, 25, 31, 32, 44, 45, 46, 75, 76.
- Etapa 6 (día/noche y clima): 5, 6, 7, 16, 20, 22, 73, 74, 77, 97.
- Etapa 7 (IA, historia y modos): todas las demás.

### Asfalto
1. Circuito del Pueblo – 3 vueltas por calles empedradas entre casas de colores.
2. Sprint de la Sierra – de la base de la montaña al mirador.
3. Bajada del Mirador – mismo camino cuesta abajo, curvas cerradas.
4. Autopista a Fondo – recta larga, gana la mayor velocidad.
5. Carrera al Atardecer – solo disponible con el sol bajo.
6. Medianoche en el Pueblo – circuito nocturno con faros y farolas.
7. Carrera bajo la Lluvia – asfalto mojado, menos agarre.
8. Vuelta Completa – recorre todo el mapa.
9. Eliminación – cada vuelta sale el último.
10. Salida en Reversa – arrancas último.
11. Circuito de la Plaza – vueltas cortas alrededor del kiosco.
12. Gran Final – se desbloquea al ganar todas.

### Tierra y rally
13. Rally del Bosque – tierra entre pinos.
14. Brecha del Río – cruzas el río varias veces.
15. Rally de Polvo – el polvo reduce la visibilidad.
16. Lodo y Lluvia – tierra mojada y resbalosa.
17. Cross Country – solo checkpoints, tú eliges la ruta.
18. Subida a la Antena – terracería empinada a la cima.
19. Saltos del Cerro – carrera con brincos grandes.
20. Rally Nocturno – tierra de noche con neblina.
21. Ruta del Rancho – entre cercas, establos y campos.
22. Contra la Tormenta – la lluvia empieza a mitad de carrera.

### Contrarreloj y desafíos
23. Radar de Velocidad – pasa a la mayor velocidad posible.
24. Zona de Velocidad – mejor velocidad promedio en un tramo.
25. Salto Largo – se mide la distancia del salto.
26. Zona de Derrape – puntos por derrapar.
27. Contra tu Fantasma – vence tu mejor tiempo.
28. Vuelta Perfecta – sin tocar nada ni salirte.
29. Sin Frenos – termina sin usar el freno.
30. Cronómetro en Reversa – cada checkpoint suma segundos.
31. Escalera al Cielo – sube la montaña en menos de X minutos.
32. Slalom de Conos – esquiva conos.
33. Derrape en la Plaza – gira alrededor del kiosco.
34. Precisión – estaciónate exacto en un cuadro.

### Exhibiciones especiales
35. Carro contra Tren.
36. Carro contra Avioneta.
37. Carro contra Motos.
38. El Cometa – persigue una luz hasta donde cae.
39. Desfile del Pueblo – carrera en fiesta con papel picado y cohetes.
40. Carrera de Leyenda – rival "famoso" muy rápido.
41. Escape del Volcán – baja la montaña con ceniza cayendo.
42. Persecución al Atardecer – helicóptero con cámara de película.

### Exploración y coleccionables
43. Graneros Olvidados – carros abandonados escondidos para restaurar.
44. Letreros de Bonus – rómpelos por todo el mapa.
45. Miradores – llega a los puntos más altos.
46. Desafío de Foto – foto de tu carro en un lugar específico (usa Modo Foto).
47. Ruta Turística – recorre los lugares más bonitos.
48. Caminos Secretos – descubre todas las carreteras.
49. Cazar al Rival – alcanza un carro que aparece al azar.
50. Tesoro Escondido – sigue pistas con fotos.

### Historia
51. El Primer Día – tutorial de manejo.
52. Entrega Urgente – paquete sin dañarlo.
53. Taxi del Pueblo – pasajeros sin chocar.
54. El Mecánico – consigue piezas por el mapa.
55. Rival del Barrio – serie de carreras hasta la final.
56. Prueba de Manejo – derrapar, frenar y saltar para entrar al festival.
57. Escolta – protege a un carro hasta su destino.
58. Llega a Tiempo – llega a una boda o fiesta antes de que empiece.
59. Doble Carro – misma carrera con deportivo y con 4x4.
60. El Festival – todas las carreras del festival en una noche.

### Pueblo y ciudad
61. Callejones – calles donde apenas cabe el carro.
62. Mercado – entre puestos sin chocar.
63. Subida de Escaleras – calles empinadas de piedra.
64. Ruta de las Iglesias – pasa por todas en orden.
65. Mañana de Tianguis – calles bloqueadas, busca otra ruta.
66. Semáforos en Verde – llega antes de que cambien.
67. Hora Pico – carrera con mucho tráfico.
68. Sin Tocar Banquetas – si subes a la banqueta, pierdes.
69. Puente Viejo – crúzalo antes de que lo cierren.
70. Callejón sin Salida – encuentra la salida del laberinto.

### Naturaleza
71. Cascada – carrera a una cascada escondida.
72. Orilla del Lago – circuito alrededor de un lago.
73. Niebla de la Sierra – visibilidad casi cero.
74. Amanecer en la Cima – llega antes de que salga el sol.
75. Ruta de los Magueyes – tierra entre campos de agave.
76. Barranca – camino junto a un precipicio.
77. Bosque Nocturno – solo faros y luciérnagas.
78. Playa – carrera sobre arena (si se amplía el mapa).
79. Cañón – entre paredes de roca.
80. Desierto – recta larga con distorsión por calor.

### Modos diferentes
81. Infectado – si te tocan, te infectas.
82. Rey de la Colina – quédate más tiempo en la cima.
83. Rompe Todo – destruye objetos en un minuto.
84. Persecución Policiaca – escapa (o persigue).
85. Carrera de Seguimiento – no pierdas de vista a un carro.
86. Combustible Limitado – recoge gasolina.
87. Sin Mapa – solo letreros del camino.
88. Carro Equivocado – gana en asfalto con camioneta vieja.
89. Relevo – cambias de carro a mitad de carrera.
90. Atrapa la Bandera – lleva banderas a tu base.

### Habilidad
91. Derrape en Equipo – junto a un carro IA sin chocar.
92. Tren de Derrapes – encadena derrapes en toda la montaña.
93. Saltos Combinados – 3 saltos seguidos sin chocar.
94. Aterrizaje Perfecto – cae en una zona marcada.
95. Velocidad Máxima – alcanza la máxima del carro.
96. Recorrido Limpio – todo el mapa sin choques.
97. Calles sin Faros – solo luz de farolas.
98. Máximo Rebase – rebasa a 20 carros.
99. Reto del Mecánico – carro dañado (menos potencia, dirección chueca).
100. Leyenda del Festival – asfalto, tierra, saltos, derrapes y noche juntos.
