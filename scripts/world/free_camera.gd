class_name FreeCamera
extends Camera3D
## Flying camera for test scenes: hold the right mouse button to look around,
## WASD to move, E/Q up and down, Shift to go faster.

@export_group("Movement")
@export var speed: float = 12.0
@export var fast_multiplier: float = 4.0
@export var acceleration: float = 8.0
@export_group("Look")
@export var mouse_sensitivity: float = 0.003

var _velocity: Vector3 = Vector3.ZERO
var _yaw: float = 0.0
var _pitch: float = 0.0


func _ready() -> void:
	_yaw = rotation.y
	_pitch = rotation.x


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch = clampf(_pitch - event.relative.y * mouse_sensitivity, -1.5, 1.5)
		rotation = Vector3(_pitch, _yaw, 0.0)


func _process(delta: float) -> void:
	var dir := Vector3.ZERO
	dir.x = Input.get_axis("steer_left", "steer_right")
	dir.z = Input.get_axis("accelerate", "brake")
	dir.y = Input.get_axis("fly_down", "fly_up")
	var target := (global_basis * dir.normalized()) * speed
	if Input.is_action_pressed("fly_fast"):
		target *= fast_multiplier
	_velocity = _velocity.lerp(target, 1.0 - exp(-acceleration * delta))
	global_position += _velocity * delta
