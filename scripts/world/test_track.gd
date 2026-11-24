class_name TestTrack
extends Node3D
## Test scene for the car and the look: golden-hour Poly Haven HDRI, low warm sun with
## shadows, a grass field, a long asphalt road and a big asphalt pad for drifting, a few
## concrete blocks for scale. Everything is built in code so the
## values below can be tuned in the Inspector (select the root node "TestTrack").

@export_group("Sky and exposure")
@export var hdri: Texture2D = preload("res://assets/hdri/kloppenheim_06_puresky_2k.hdr")
@export var sky_energy: float = 1.0
@export_range(0.1, 4.0) var exposure: float = 1.0
@export_enum("Linear", "Reinhard", "Filmic", "ACES", "AgX") var tonemap: int = 4

@export_group("Sun")
@export var sun_rotation_deg: Vector3 = Vector3(-14.0, 139.0, 0.0)   ## matches the sun in the HDRI
@export var sun_energy: float = 2.0
@export var sun_color: Color = Color(1.0, 0.8, 0.58)
@export var shadow_distance: float = 180.0

@export_group("Effects")
@export var ssao_enabled: bool = true
@export var ssr_enabled: bool = true
@export var glow_enabled: bool = true
@export var fog_enabled: bool = true
@export var fog_density: float = 0.0012

@export_group("Ground")
@export var ground_size: float = 600.0
@export var road_length: float = 500.0
@export var road_width: float = 12.0
@export var pad_size: float = 170.0
@export var grass_material: Material = preload("res://assets/materials/aerial_grass_rock.tres")
@export var asphalt_material: Material = preload("res://assets/materials/asphalt_02.tres")


func _ready() -> void:
	_build_environment()
	_build_sun()
	_build_ground()
	_build_blocks()


func _build_environment() -> void:
	var sky_mat := PanoramaSkyMaterial.new()
	sky_mat.panorama = hdri
	sky_mat.energy_multiplier = sky_energy
	var sky := Sky.new()
	sky.sky_material = sky_mat
	sky.radiance_size = Sky.RADIANCE_SIZE_128          # cheap reflections, enough for this GPU

	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = tonemap as Environment.ToneMapper
	env.tonemap_exposure = exposure
	env.ssao_enabled = ssao_enabled
	env.ssao_radius = 1.5
	env.ssao_intensity = 1.6
	env.ssr_enabled = ssr_enabled
	env.ssr_max_steps = 32
	env.glow_enabled = glow_enabled
	env.glow_intensity = 0.5
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.2
	env.fog_enabled = fog_enabled
	env.fog_light_color = Color(1.0, 0.82, 0.64)
	env.fog_density = fog_density
	env.fog_sky_affect = 0.15
	env.fog_aerial_perspective = 0.6
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.05
	env.adjustment_saturation = 1.12

	var world_env := WorldEnvironment.new()
	world_env.name = "WorldEnvironment"
	world_env.environment = env
	add_child(world_env)


func _build_sun() -> void:
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = sun_rotation_deg
	sun.light_energy = sun_energy
	sun.light_color = sun_color
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = shadow_distance
	sun.directional_shadow_blend_splits = true
	sun.light_angular_distance = 0.5                     # slightly soft shadow edges
	add_child(sun)


func _build_ground() -> void:
	var ground := _static_box("Ground", Vector3(ground_size, 1.0, ground_size), Vector3(0.0, -0.5, 0.0), grass_material)
	ground.set_meta("surface", "grass")
	var road := _static_box("Road", Vector3(road_width, 0.1, road_length), Vector3(0.0, 0.05, 0.0), asphalt_material)
	road.set_meta("surface", "asphalt")
	var pad := _static_box("DriftPad", Vector3(pad_size, 0.1, pad_size), Vector3(road_width * 0.5 + 20.0 + pad_size * 0.5, 0.05, -60.0), asphalt_material)
	pad.set_meta("surface", "asphalt")
	var dirt := _static_box("DirtPatch", Vector3(60.0, 0.1, 120.0), Vector3(-(road_width * 0.5 + 50.0), 0.05, 60.0), grass_material)
	dirt.set_meta("surface", "dirt")


func _build_blocks() -> void:
	var concrete := StandardMaterial3D.new()
	concrete.albedo_color = Color(0.62, 0.61, 0.58)
	concrete.roughness = 0.85
	for i: int in 6:
		var z := -200.0 + i * 80.0
		var side := 1.0 if i % 2 == 0 else -1.0
		_static_box("Block%d" % i, Vector3(4.0, 2.0 + i * 0.8, 4.0), Vector3(side * (road_width * 0.5 + 8.0), 1.0 + i * 0.4, z), concrete)


func _static_box(node_name: String, size: Vector3, pos: Vector3, mat: Material) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = pos
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	box.material = mat
	mesh.mesh = box
	body.add_child(mesh)
	var shape := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	shape.shape = bs
	body.add_child(shape)
	add_child(body)
	return body
