class_name CarWheel
extends RayCast3D
## One wheel: a ray from the suspension mount straight down. Computes the spring and
## damper force, and the tire forces (grip) at the contact point. The car calls
## update_wheel() every physics step; the wheel never applies forces by itself.

signal surface_changed(surface: StringName)

@export var is_front: bool = false
@export var is_left: bool = false
@export var is_driven: bool = true

# filled in by CarController
var car: RigidBody3D
var radius: float = 0.34
var rest_length: float = 0.32

# state, read by the car, the effects and the HUD
var grounded: bool = false
var compression: float = 0.0          # metres
var tire_load: float = 0.0                 # newtons pressing the tire on the ground
var contact_point: Vector3 = Vector3.ZERO
var contact_normal: Vector3 = Vector3.UP
var surface: StringName = &"asphalt"
var steer_angle: float = 0.0          # radians, positive = left
var slip_lateral: float = 0.0         # m/s sideways at the contact patch
var slip_longitudinal: float = 0.0    # 0..1, how much the tire is spinning or locking
var forward_speed: float = 0.0        # m/s along the wheel
var spin_angle: float = 0.0

var _prev_compression: float = 0.0
var _visual: Node3D


func setup(p_car: RigidBody3D, p_radius: float, p_rest: float, visual: Node3D) -> void:
	car = p_car
	radius = p_radius
	rest_length = p_rest
	target_position = Vector3(0.0, -(rest_length + radius), 0.0)
	add_exception(car)
	enabled = true
	_visual = visual
	add_child(_visual)


## Suspension: returns the spring force along the car's up axis (newtons, >= 0).
func update_suspension(delta: float, stiffness: float, bump: float, rebound: float) -> float:
	force_raycast_update()
	grounded = is_colliding()
	if not grounded:
		compression = 0.0
		_prev_compression = 0.0
		tire_load = 0.0
		return 0.0
	contact_point = get_collision_point()
	contact_normal = get_collision_normal()
	var dist: float = global_position.distance_to(contact_point)
	compression = clampf(rest_length + radius - dist, 0.0, rest_length)
	var vel: float = (compression - _prev_compression) / delta
	_prev_compression = compression
	var damping: float = bump if vel > 0.0 else rebound
	tire_load = maxf(stiffness * compression + damping * vel, 0.0)
	var col: Object = get_collider()
	var s: StringName = &"asphalt"
	if col is Node and (col as Node).has_meta(&"surface"):
		s = StringName((col as Node).get_meta(&"surface"))
	if s != surface:
		surface = s
		surface_changed.emit(surface)
	return tire_load


## Where the wheel centre sits right now (for the visual and the effects).
func wheel_center() -> Vector3:
	var travel: float = rest_length - compression
	return global_position - car.global_basis.y * travel


func update_visual(delta: float) -> void:
	if _visual == null:
		return
	_visual.position = Vector3(0.0, -(rest_length - compression), 0.0)
	_visual.rotation = Vector3.ZERO
	_visual.rotate_y(steer_angle)
	spin_angle = wrapf(spin_angle - forward_speed / radius * delta, -PI, PI)
	_visual.rotate_object_local(Vector3.RIGHT, spin_angle)
