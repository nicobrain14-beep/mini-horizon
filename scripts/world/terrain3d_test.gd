class_name Terrain3DTest
extends Node3D
## Phase 0: checks that Terrain3D loads and draws on the development Mac.
## Builds a 1 x 1 km Terrain3D in code (rolling hills, a flat start area), paints it with
## real Poly Haven grass and rock (the auto shader puts rock on slopes) and drops the car on it.

@export_group("Terrain")
@export var size_m: int = 1024
@export var hill_height: float = 45.0
@export var noise_frequency: float = 0.0035
@export var flat_radius: float = 70.0
@export var grass_uv_scale: float = 0.08
@export var rock_uv_scale: float = 0.06
@export_group("Sky")
@export var hdri: Texture2D = preload("res://assets/hdri/kloppenheim_06_puresky_2k.hdr")
@export var sun_rotation_deg: Vector3 = Vector3(-14.0, 139.0, 0.0)

var terrain: Terrain3D


func _ready() -> void:
	_build_sky()
	_build_terrain()
	_spawn_car()


func _build_terrain() -> void:
	terrain = Terrain3D.new()
	terrain.name = "Terrain3D"
	terrain.region_size = Terrain3D.SIZE_1024
	terrain.free_editor_textures = false
	add_child(terrain)
	terrain.set_meta(&"surface", "grass")
	terrain.material.world_background = Terrain3DMaterial.NONE
	terrain.material.auto_shader_enabled = true
	# auto shader: "base" goes on slopes, "overlay" on flat ground
	terrain.material.set_shader_param("auto_slope", 3.0)
	terrain.material.set_shader_param("auto_height_reduction", 0.05)
	terrain.material.set_shader_param("auto_base_texture", 0)
	terrain.material.set_shader_param("auto_overlay_texture", 1)
	terrain.material.set_shader_param("blend_sharpness", 0.9)
	terrain.assets.set_texture_asset(0, _texture_asset("Rock", "rock", rock_uv_scale))
	terrain.assets.set_texture_asset(1, _texture_asset("Grass", "grass", grass_uv_scale))
	var noise := FastNoiseLite.new()
	noise.frequency = noise_frequency
	noise.fractal_octaves = 5
	var img := Image.create_empty(size_m, size_m, false, Image.FORMAT_RF)
	var half: float = size_m * 0.5
	for z: int in size_m:
		for x: int in size_m:
			var d: float = Vector2(x - half, z - half).length()
			var flat: float = smoothstep(flat_radius, flat_radius * 2.5, d)
			img.set_pixel(x, z, Color(noise.get_noise_2d(x, z) * flat, 0.0, 0.0, 1.0))
	terrain.data.import_images([img, null, null], Vector3(-half, 0.0, -half), 0.0, hill_height)


func _texture_asset(asset_name: String, file: String, uv_scale: float) -> Terrain3DTextureAsset:
	var ta := Terrain3DTextureAsset.new()
	ta.name = asset_name
	ta.albedo_texture = load("res://assets/textures/terrain/%s_alb_h.webp" % file)
	ta.normal_texture = load("res://assets/textures/terrain/%s_nrm_r.webp" % file)
	ta.uv_scale = uv_scale
	return ta


func _spawn_car() -> void:
	var car: Node3D = load("res://scenes/vehicles/car.tscn").instantiate()
	car.name = "Car"
	car.position = Vector3(0.0, 2.5, 0.0)
	add_child(car)
	var cam := CarCamera.new()
	cam.name = "CarCamera"
	cam.car_path = NodePath("../Car")
	add_child(cam)
	var hud := CarHud.new()
	hud.name = "CarHud"
	hud.car_path = NodePath("../Car")
	add_child(hud)


func _build_sky() -> void:
	var sky_mat := PanoramaSkyMaterial.new()
	sky_mat.panorama = hdri
	var sky := Sky.new()
	sky.sky_material = sky_mat
	sky.radiance_size = Sky.RADIANCE_SIZE_128
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssr_enabled = true
	env.glow_enabled = true
	env.glow_intensity = 0.5
	env.fog_enabled = true
	env.fog_light_color = Color(1.0, 0.82, 0.64)
	env.fog_density = 0.0008
	env.fog_aerial_perspective = 0.6
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = sun_rotation_deg
	sun.light_energy = 2.0
	sun.light_color = Color(1.0, 0.8, 0.58)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 180.0
	add_child(sun)
