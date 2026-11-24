class_name CarBodyVisual
extends Node3D
## Temporary car body made of simple shapes, until a real .glb model exists.
## Proportions of a generic two-door sports coupe (4.4 m x 1.86 m), front is -Z.
## Paint uses StandardMaterial3D clearcoat (metallic base + glossy lacquer).

@export var paint_color: Color = Color(0.95, 0.72, 0.05)
@export_range(0.0, 1.0) var paint_metallic: float = 0.55
@export_range(0.0, 1.0) var paint_roughness: float = 0.28

static var _tire_mat: StandardMaterial3D
static var _rim_mat: StandardMaterial3D


func _ready() -> void:
	var paint := StandardMaterial3D.new()
	paint.albedo_color = paint_color
	paint.metallic = paint_metallic
	paint.roughness = paint_roughness
	paint.clearcoat_enabled = true
	paint.clearcoat = 1.0
	paint.clearcoat_roughness = 0.04
	var black := _mat(Color(0.03, 0.035, 0.04), 0.3, 0.55)
	var glass := _mat(Color(0.02, 0.03, 0.04), 0.4, 0.04)
	var carbon := _mat(Color(0.05, 0.05, 0.055), 0.5, 0.25)
	carbon.clearcoat_enabled = true

	# lower body, tapered nose and tail, cabin
	_box(Vector3(1.86, 0.46, 4.36), Vector3(0.0, 0.16, 0.0), paint)
	_box(Vector3(1.8, 0.16, 1.2), Vector3(0.0, 0.43, -1.45), paint, Vector3(-6.0, 0.0, 0.0))      # hood
	_box(Vector3(1.8, 0.2, 0.9), Vector3(0.0, 0.45, 1.65), paint, Vector3(4.0, 0.0, 0.0))         # deck
	_box(Vector3(1.5, 0.42, 1.95), Vector3(0.0, 0.62, 0.22), glass)                               # greenhouse
	_box(Vector3(1.42, 0.05, 1.3), Vector3(0.0, 0.855, 0.3), paint)                               # roof
	_box(Vector3(1.9, 0.1, 4.4), Vector3(0.0, -0.06, 0.0), carbon)                                # skirts and splitter line
	_box(Vector3(1.7, 0.05, 0.42), Vector3(0.0, 0.72, 1.92), carbon)                              # rear wing
	for x: float in [-0.62, 0.62]:
		_box(Vector3(0.06, 0.2, 0.3), Vector3(x, 0.6, 1.92), carbon)
	# arches (dark) so the wheels read
	for z: float in [-1.31, 1.31]:
		for x: float in [-0.9, 0.9]:
			_box(Vector3(0.12, 0.42, 0.92), Vector3(x, 0.08, z), black)
	# lights: emissive so they glow through bloom at dusk
	var head := _mat(Color(1.0, 0.97, 0.9), 0.0, 0.2)
	head.emission_enabled = true
	head.emission = Color(1.0, 0.95, 0.85)
	head.emission_energy_multiplier = 3.0
	var tail := _mat(Color(0.6, 0.02, 0.03), 0.0, 0.3)
	tail.emission_enabled = true
	tail.emission = Color(1.0, 0.05, 0.05)
	tail.emission_energy_multiplier = 2.5
	for x: float in [-0.62, 0.62]:
		_box(Vector3(0.42, 0.07, 0.05), Vector3(x, 0.33, -2.19), head)
	_box(Vector3(1.5, 0.06, 0.05), Vector3(0.0, 0.38, 2.19), tail)
	_box(Vector3(1.2, 0.14, 0.06), Vector3(0.0, 0.08, -2.2), black)                                # grille


func _box(size: Vector3, pos: Vector3, mat: Material, rot_deg: Vector3 = Vector3.ZERO) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	m.mesh = b
	m.material_override = mat
	m.position = pos
	m.rotation_degrees = rot_deg
	add_child(m)
	return m


static func _mat(c: Color, metallic: float, rough: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.metallic = metallic
	m.roughness = rough
	return m


## A wheel: tire, rim and a brake disc, built around its own centre (axle along X).
static func make_wheel(radius: float, is_left: bool) -> Node3D:
	if _tire_mat == null:
		_tire_mat = _mat(Color(0.035, 0.035, 0.04), 0.0, 0.82)
		_rim_mat = _mat(Color(0.75, 0.76, 0.78), 1.0, 0.22)
	var root := Node3D.new()
	var tire := MeshInstance3D.new()
	var tm := CylinderMesh.new()
	tm.top_radius = radius
	tm.bottom_radius = radius
	tm.height = 0.26
	tm.radial_segments = 28
	tire.mesh = tm
	tire.material_override = _tire_mat
	tire.rotation_degrees = Vector3(0.0, 0.0, 90.0)
	root.add_child(tire)
	var rim := MeshInstance3D.new()
	var rm := CylinderMesh.new()
	rm.top_radius = radius * 0.66
	rm.bottom_radius = radius * 0.66
	rm.height = 0.02
	rm.radial_segments = 24
	rim.mesh = rm
	rim.material_override = _rim_mat
	rim.rotation_degrees = Vector3(0.0, 0.0, 90.0)
	rim.position = Vector3(-0.125 if is_left else 0.125, 0.0, 0.0)
	root.add_child(rim)
	for i: int in 5:                                      # spokes, so you can see it spin
		var sp := MeshInstance3D.new()
		var sb := BoxMesh.new()
		sb.size = Vector3(0.03, radius * 1.25, 0.05)
		sp.mesh = sb
		sp.material_override = _rim_mat
		sp.position = Vector3(-0.13 if is_left else 0.13, 0.0, 0.0)
		sp.rotation = Vector3(TAU / 5.0 * i, 0.0, 0.0)
		root.add_child(sp)
	return root
