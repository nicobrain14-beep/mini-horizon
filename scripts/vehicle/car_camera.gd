class_name CarCamera
extends Camera3D
## Chase and hood cameras for a CarController (C switches).
## Follows the car's INTERPOLATED transform in _process (physics interpolation is on), so it
## never jitters against the 120 Hz physics. Smoothing uses 1 - exp(-rate * dt): the same feel
## at any frame rate. Speed pulls the camera back and widens the FOV; shake is trauma^2 with
## summed sines, added last on top of the follow.

enum Mode { CHASE, HOOD }

@export var car_path: NodePath
@export var mode: Mode = Mode.CHASE

@export_group("Chase")
@export var distance_slow: float = 5.4
@export var distance_fast: float = 7.0
@export var height_slow: float = 1.65
@export var height_fast: float = 1.85
@export var top_speed_kmh: float = 240.0           ## where distance, FOV and shake reach their max
@export var yaw_rate: float = 6.0                  ## how fast the camera swings behind the car
@export_range(0.0, 1.0) var follow_velocity: float = 0.45   ## 0 = behind the nose, 1 = behind the motion (shows drifts)
@export var height_rate: float = 7.0               ## smooths suspension bounce out of the view
@export var look_ahead: float = 2.5
@export var collision_margin: float = 0.3

@export_group("Hood")
@export var hood_offset: Vector3 = Vector3(0.0, 0.98, -0.35)
@export var hood_fov: float = 78.0

@export_group("FOV")
@export var fov_slow: float = 66.0
@export var fov_fast: float = 86.0
@export var fov_rate: float = 4.0
@export var shift_punch: float = 2.5               ## degrees added on each upshift

@export_group("Shake")
@export_range(0.0, 1.0) var shake_strength: float = 1.0    ## player setting: 0 turns shake off
@export var speed_trauma: float = 0.4              ## steady rumble at top speed
@export var landing_trauma: float = 0.7
@export var trauma_decay: float = 1.6
@export var max_offset: Vector3 = Vector3(0.05, 0.04, 0.0)
@export var max_roll_deg: float = 0.6

var _car: CarController
var _yaw: float = 0.0
var _height_y: float = 0.0
var _distance: float = 5.4
var _fov_extra: float = 0.0
var _base_fov: float = 66.0
var _trauma: float = 0.0
var _t: float = 0.0
var _snap: bool = true


func _ready() -> void:
	top_level = true
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF   # moved in _process
	_car = get_node(car_path) as CarController
	_car.gear_changed.connect(_on_gear_changed)
	_car.landed.connect(func(impact: float) -> void: add_trauma(impact * landing_trauma))
	_car.car_reset.connect(func() -> void: _snap = true)
	make_current()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("camera_next"):
		mode = Mode.HOOD if mode == Mode.CHASE else Mode.CHASE
		_snap = true


func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount, 0.0, 1.0)


func _on_gear_changed(new_gear: int) -> void:
	if new_gear > 1:
		_fov_extra += shift_punch


func _process(delta: float) -> void:
	if _car == null:
		return
	var t: Transform3D = _car.get_global_transform_interpolated()
	var kmh: float = _car.speed_kmh()
	var speed_t: float = clampf(kmh / top_speed_kmh, 0.0, 1.0)
	var target_fov: float
	if mode == Mode.HOOD:
		global_transform = t * Transform3D(Basis.IDENTITY, hood_offset)
		target_fov = hood_fov + speed_t * 8.0
	else:
		_chase(t, speed_t, delta)
		target_fov = lerpf(fov_slow, fov_fast, speed_t * speed_t)
	# FOV with a punch that eases out after each upshift
	_fov_extra = lerpf(_fov_extra, 0.0, 1.0 - exp(-3.0 * delta))
	_base_fov = target_fov if _snap else lerpf(_base_fov, target_fov, 1.0 - exp(-fov_rate * delta))
	fov = _base_fov + _fov_extra
	_snap = false
	_shake(delta, speed_t)


func _chase(t: Transform3D, speed_t: float, delta: float) -> void:
	var fwd: Vector3 = -t.basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	var vel: Vector3 = _car.linear_velocity
	vel.y = 0.0
	var dir: Vector3 = fwd
	if vel.length() > 4.0 and vel.dot(fwd) > 0.0:
		dir = fwd.lerp(vel.normalized(), follow_velocity).normalized()
	var target_yaw: float = atan2(-dir.x, -dir.z)
	if _snap:
		_yaw = target_yaw
		_height_y = t.origin.y
		_distance = distance_slow
	_yaw = lerp_angle(_yaw, target_yaw, 1.0 - exp(-yaw_rate * delta))
	_height_y = lerpf(_height_y, t.origin.y, 1.0 - exp(-height_rate * delta))
	_distance = lerpf(_distance, lerpf(distance_slow, distance_fast, speed_t), 1.0 - exp(-2.5 * delta))
	var back := Vector3(sin(_yaw), 0.0, cos(_yaw))
	var focus := Vector3(t.origin.x, _height_y + 0.85, t.origin.z)
	var height: float = lerpf(height_slow, height_fast, speed_t)
	var want: Vector3 = Vector3(t.origin.x, _height_y, t.origin.z) + back * _distance + Vector3.UP * height
	# keep the camera out of walls: pull it in along the line to the car
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(focus, want)
	q.exclude = [_car.get_rid()]
	var hit: Dictionary = space.intersect_ray(q)
	if not hit.is_empty():
		want = (hit["position"] as Vector3) + (focus - want).normalized() * collision_margin
	global_position = want
	look_at(focus - back * look_ahead, Vector3.UP)


func _shake(delta: float, speed_t: float) -> void:
	_trauma = maxf(_trauma - trauma_decay * delta, 0.0)
	var base: float = speed_trauma * speed_t * speed_t
	var tr: float = maxf(_trauma, base)
	var s: float = tr * tr * shake_strength
	if s <= 0.0001:
		return
	_t += delta * 28.0
	var b: Basis = global_basis
	global_position += b.x * max_offset.x * s * sin(_t * 1.7) + b.y * max_offset.y * s * sin(_t * 2.3)
	rotate_object_local(Vector3.FORWARD, deg_to_rad(max_roll_deg) * s * sin(_t * 1.1))
