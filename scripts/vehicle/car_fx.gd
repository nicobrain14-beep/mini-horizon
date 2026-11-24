class_name CarFx
extends Node3D
## Drift and braking effects: tire smoke (or dust on dirt/grass) at each sliding wheel,
## and skid marks on asphalt. Visual only; reads the wheels, never changes the physics.

@export_group("Smoke")
@export var smoke_amount: int = 40
@export var smoke_lifetime: float = 2.4
@export var smoke_color: Color = Color(0.82, 0.82, 0.84, 0.55)
@export var dust_color: Color = Color(0.55, 0.45, 0.32, 0.5)
@export_group("Skid marks")
@export var max_marks: int = 1600                     ## quads in the ring buffer (one draw call)
@export var mark_width: float = 0.24
@export var mark_alpha: float = 0.6
@export var min_segment: float = 0.35                 ## metres between quads
@export_group("Thresholds")
@export var slide_start: float = 2.2                  ## sideways m/s before the tire smokes
@export var slide_full: float = 7.0

var _car: CarController
var _smokes: Array[GPUParticles3D] = []
var _last_mark: Array[Vector3] = []
var _marking: Array[bool] = []
var _marks: MultiMeshInstance3D
var _next_mark: int = 0


func _ready() -> void:
	_car = get_parent() as CarController
	_build_marks()
	for w: CarWheel in _car.wheels:
		_smokes.append(_make_smoke())
		_last_mark.append(Vector3.ZERO)
		_marking.append(false)


func _physics_process(_delta: float) -> void:
	for i: int in _car.wheels.size():
		var w: CarWheel = _car.wheels[i]
		var amount: float = _slide_amount(w)
		var p: GPUParticles3D = _smokes[i]
		var on_dirt: bool = w.surface == &"dirt" or w.surface == &"grass"
		p.emitting = amount > 0.05
		if p.emitting:
			p.global_position = w.contact_point + Vector3.UP * 0.15
			p.amount_ratio = clampf(amount, 0.25, 1.0)
			var col: Color = dust_color if on_dirt else smoke_color
			(p.draw_pass_1.surface_get_material(0) as StandardMaterial3D).albedo_color = col
		if amount > 0.15 and not on_dirt:
			_add_mark(i, w, amount)
		else:
			_marking[i] = false


func _slide_amount(w: CarWheel) -> float:
	if not w.grounded or absf(w.forward_speed) + absf(w.slip_lateral) < 2.0:
		return 0.0
	var side: float = clampf((absf(w.slip_lateral) - slide_start) / (slide_full - slide_start), 0.0, 1.0)
	var spin: float = w.slip_longitudinal * 1.5
	if _car.handbrake and not w.is_front:
		spin = maxf(spin, 0.6)
	return clampf(maxf(side, spin), 0.0, 1.0)


func _make_smoke() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.top_level = true
	p.local_coords = false
	p.amount = smoke_amount
	p.lifetime = smoke_lifetime
	p.emitting = false
	p.visibility_aabb = AABB(Vector3(-8, -2, -8), Vector3(16, 8, 16))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3(0.0, 1.0, 0.0)
	pm.spread = 60.0
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 2.0
	pm.gravity = Vector3(0.0, 0.35, 0.0)               # warm smoke rises a little
	pm.damping_min = 0.8
	pm.damping_max = 1.6
	pm.scale_min = 0.8
	pm.scale_max = 1.3
	var grow := Curve.new()
	grow.add_point(Vector2(0.0, 0.6))
	grow.add_point(Vector2(1.0, 3.2))
	var grow_tex := CurveTexture.new()
	grow_tex.curve = grow
	pm.scale_curve = grow_tex
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0.9))
	fade.set_color(1, Color(1, 1, 1, 0.0))
	var fade_tex := GradientTexture1D.new()
	fade_tex.gradient = fade
	pm.color_ramp = fade_tex
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(1.1, 1.1)
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.albedo_color = smoke_color
	mat.albedo_texture = _soft_puff()
	mat.proximity_fade_enabled = true                   # no hard line where smoke meets the road
	mat.proximity_fade_distance = 0.6
	quad.material = mat
	p.draw_pass_1 = quad
	add_child(p)
	return p


func _soft_puff() -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(0.5, 0.0)
	t.width = 64
	t.height = 64
	return t


func _build_marks() -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.instance_count = max_marks
	mm.visible_instance_count = 0
	var plane := PlaneMesh.new()
	plane.size = Vector2(1.0, 1.0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.02, 0.02, 0.02)
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.roughness = 0.6
	plane.material = mat
	mm.mesh = plane
	_marks = MultiMeshInstance3D.new()
	_marks.multimesh = mm
	_marks.top_level = true
	_marks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_marks.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	add_child(_marks)
	_marks.global_transform = Transform3D.IDENTITY


func _add_mark(i: int, w: CarWheel, amount: float) -> void:
	var p: Vector3 = w.contact_point + w.contact_normal * 0.012
	if not _marking[i]:
		_marking[i] = true
		_last_mark[i] = p
		return
	var seg: Vector3 = p - _last_mark[i]
	var length: float = seg.length()
	if length < min_segment:
		return
	if length > 3.0:                                    # teleport or jump: start a new line
		_last_mark[i] = p
		return
	var z: Vector3 = seg / length
	var y: Vector3 = w.contact_normal
	var x: Vector3 = y.cross(z).normalized()
	var basis := Basis(x * mark_width, y, z * (length + 0.05))
	var mm: MultiMesh = _marks.multimesh
	mm.set_instance_transform(_next_mark, Transform3D(basis, (p + _last_mark[i]) * 0.5))
	mm.set_instance_color(_next_mark, Color(1, 1, 1, mark_alpha * clampf(amount, 0.3, 1.0)))
	_next_mark = (_next_mark + 1) % max_marks
	if mm.visible_instance_count < max_marks:
		mm.visible_instance_count = max_marks if _next_mark == 0 else maxi(mm.visible_instance_count, _next_mark)
	_last_mark[i] = p
