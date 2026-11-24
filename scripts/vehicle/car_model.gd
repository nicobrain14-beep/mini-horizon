class_name CarModel
extends Node3D
## Shows an imported car model (.glb made with tools/blender/car_prep.py): a "Body" mesh
## and four "Wheel_FL/FR/RL/RR" meshes with their origin at the wheel centre.
## Reports the wheel layout to the car, hands the wheel meshes to the CarWheel nodes,
## repaints the body with the clear-coat flake shader and drives the lights.

const WHEEL_NAMES: Array[String] = ["Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"]

@export var paint_color: Color = Color(0.95, 0.72, 0.05)
@export var paint_shader: Shader = preload("res://assets/shaders/car_paint.gdshader")
@export var paint_material_name: String = "car-body"
@export var tail_material_names: PackedStringArray = PackedStringArray(["Glass_-_Red", "Glass_-_Red_-_Rough"])
@export var head_material_names: PackedStringArray = PackedStringArray(["Glass_-_Clear_-_Bumps"])
@export var tail_energy: float = 1.2
@export var brake_energy: float = 5.0
@export var head_energy: float = 2.5

var wheel_centers: Array[Vector3] = []          # model space, FL FR RL RR
var wheel_radius: float = 0.34
var _wheels: Array[Node3D] = []
var _tail_mats: Array[StandardMaterial3D] = []


## Instances the model and reads the wheels. Call before the car builds its wheels.
func load_model(scene: PackedScene) -> void:
	var root: Node3D = scene.instantiate()
	add_child(root)
	for wn: String in WHEEL_NAMES:
		var w: Node3D = root.find_child(wn, true, false)
		assert(w != null, "car model has no node " + wn)
		wheel_centers.append(w.position)
		_wheels.append(w)
	var mi := _wheels[0] as MeshInstance3D
	if mi:
		wheel_radius = mi.get_aabb().size.y * 0.5
	for n: Node in root.find_children("*", "MeshInstance3D", true, false):
		_setup_materials(n as MeshInstance3D)


## Takes a wheel mesh out of the model so a CarWheel can spin and steer it.
func take_wheel(index: int) -> Node3D:
	var w: Node3D = _wheels[index]
	w.get_parent().remove_child(w)
	w.transform = Transform3D.IDENTITY
	var pivot := Node3D.new()
	pivot.add_child(w)
	return pivot


func set_braking(amount: float) -> void:
	for m: StandardMaterial3D in _tail_mats:
		m.emission_energy_multiplier = lerpf(tail_energy, brake_energy, clampf(amount, 0.0, 1.0))


func _setup_materials(mi: MeshInstance3D) -> void:
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	for i: int in mi.mesh.get_surface_count():
		var src := mi.get_active_material(i) as StandardMaterial3D
		if src == null:
			continue
		var n: String = src.resource_name
		if n == paint_material_name:
			var sm := ShaderMaterial.new()
			sm.shader = paint_shader
			sm.set_shader_parameter("albedo_tex", src.albedo_texture)
			sm.set_shader_parameter("orm_tex", src.roughness_texture if src.roughness_texture else src.metallic_texture)
			sm.set_shader_parameter("normal_tex", src.normal_texture)
			sm.set_shader_parameter("paint_color", paint_color)
			mi.set_surface_override_material(i, sm)
		elif n in tail_material_names:
			var m := src.duplicate() as StandardMaterial3D
			m.emission_enabled = true
			m.emission = Color(1.0, 0.04, 0.03)
			m.emission_energy_multiplier = tail_energy
			mi.set_surface_override_material(i, m)
			_tail_mats.append(m)
		elif n in head_material_names:
			var h := src.duplicate() as StandardMaterial3D
			h.emission_enabled = true
			h.emission = Color(1.0, 0.96, 0.88)
			h.emission_energy_multiplier = head_energy
			mi.set_surface_override_material(i, h)
