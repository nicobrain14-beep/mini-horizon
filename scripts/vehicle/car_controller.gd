class_name CarController
extends RigidBody3D
## Arcade-with-weight car (Horizon style) on a RigidBody3D with four ray wheels.
## Each physics step: suspension per wheel, then tire forces (grip circle per wheel),
## engine and automatic gearbox, brakes, handbrake drift, assists, drag.
## Forward is -Z. All tuning values are exports.

signal gear_changed(gear: int)
signal landed(impact: float)          ## all wheels back on the ground after a jump; impact 0..1
signal car_reset                      ## teleported (R or flipped): cameras should cut, not glide

enum Drivetrain { RWD, AWD, FWD }

@export_group("Body")
@export var car_mass: float = 1350.0
@export var center_of_mass_offset: Vector3 = Vector3(0.0, -0.32, 0.05)
@export var wheelbase: float = 2.62
@export var track_width: float = 1.62
@export var mount_height: float = 0.1
@export var paint_color: Color = Color(0.95, 0.72, 0.05)

@export_group("Engine")
@export var max_torque: float = 470.0            ## Nm at the peak of the curve
@export var torque_curve: Curve                  ## x: rpm / redline (0..1), y: share of max torque
@export var idle_rpm: float = 900.0
@export var redline_rpm: float = 7400.0
@export var engine_braking: float = 900.0        ## N of drag when off the throttle
@export var drivetrain: Drivetrain = Drivetrain.RWD
@export var drivetrain_efficiency: float = 0.85

@export_group("Gearbox")
@export var gear_ratios: PackedFloat32Array = PackedFloat32Array([3.3, 2.2, 1.62, 1.27, 1.03, 0.86])
@export var reverse_ratio: float = 3.1
@export var final_drive: float = 3.9
@export var shift_up_rpm: float = 6900.0
@export var shift_down_rpm: float = 3200.0
@export var shift_time: float = 0.16

@export_group("Brakes")
@export var brake_force: float = 15000.0          ## N, all four wheels together
@export_range(0.0, 1.0) var brake_bias_front: float = 0.62
@export var handbrake_force: float = 4500.0

@export_group("Steering")
@export var max_steer_deg: float = 36.0
@export var high_speed_steer_deg: float = 9.0
@export var steer_falloff_kmh: float = 170.0
@export var steer_speed: float = 5.0             ## how fast the wheels turn (per second)
@export_range(0.0, 1.0) var countersteer_assist: float = 0.6

@export_group("Suspension")
@export var wheel_radius: float = 0.34
@export var rest_length: float = 0.3
@export var spring_stiffness: float = 32000.0    ## N/m per wheel
@export var damping_bump: float = 3600.0
@export var damping_rebound: float = 4400.0
@export var anti_roll: float = 9000.0            ## N/m between left and right

@export_group("Tires")
@export var front_grip: float = 1.3
@export var rear_grip: float = 1.25
@export var peak_slip_deg: float = 7.0           ## slip angle where grip is highest
@export_range(0.1, 1.0) var slide_grip: float = 0.78   ## grip left when fully sideways
@export var surface_grip: Dictionary = {"asphalt": 1.0, "wet": 0.72, "dirt": 0.68, "grass": 0.55}

@export_group("Drift")
## Easy drift: a tap of the handbrake at speed while steering kicks the tail out and starts
## a slide that throttle holds and countersteer (or lifting off) ends.
@export_range(0.0, 1.0) var handbrake_rear_grip: float = 0.32
@export_range(0.0, 1.0) var power_oversteer: float = 0.35   ## rear grip lost at full throttle while sliding
@export_range(1.0, 3.0) var drift_oversteer_boost: float = 1.7   ## power oversteer multiplier while drifting
@export var drift_kick: float = 0.55             ## yaw rate (rad/s) added when the handbrake starts a drift
@export var drift_min_kmh: float = 30.0
@export var drift_max_angle_deg: float = 40.0    ## drift assist stops the car rotating further than this
@export_range(0.0, 5.0) var drift_assist: float = 2.5

@export_group("Assists")
@export var traction_control: bool = true
@export var stability_control: bool = true
@export_range(0.0, 2.0) var stability_strength: float = 0.6

@export_group("Aero")
@export var drag_coefficient: float = 0.38       ## F = c * v^2
@export var rolling_resistance: float = 14.0     ## F = c * v
@export var downforce: float = 0.9               ## N per (m/s)^2

# read by the camera, HUD, effects and sound
var throttle: float = 0.0
var brake: float = 0.0
var steer_input: float = 0.0
var handbrake: bool = false
var gear: int = 1                                 # -1 reverse, 0 neutral, 1..n
var rpm: float = 900.0
var speed: float = 0.0                            # m/s, signed along forward
var wheels: Array[CarWheel] = []
var drifting: bool = false

var _shift_timer: float = 0.0
var _steer: float = 0.0
var _flipped_time: float = 0.0
var _air_time: float = 0.0
var _fall_speed: float = 0.0
var _drift_time: float = 0.0
var _beta: float = 0.0                    # body slip angle (rad, absolute)


func _ready() -> void:
	if torque_curve == null:
		torque_curve = Curve.new()
		torque_curve.add_point(Vector2(0.0, 0.55))
		torque_curve.add_point(Vector2(0.35, 0.9))
		torque_curve.add_point(Vector2(0.65, 1.0))
		torque_curve.add_point(Vector2(0.9, 0.92))
		torque_curve.add_point(Vector2(1.0, 0.8))
	mass = car_mass
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	center_of_mass = center_of_mass_offset
	continuous_cd = true
	can_sleep = false
	angular_damp = 0.4
	_build_collision()
	var visual := CarBodyVisual.new()
	visual.name = "Body"
	visual.paint_color = paint_color
	add_child(visual)
	_build_wheels()
	var fx := CarFx.new()
	fx.name = "Fx"
	add_child(fx)


func _build_collision() -> void:
	var lower := CollisionShape3D.new()
	var lb := BoxShape3D.new()
	lb.size = Vector3(1.82, 0.5, 4.3)
	lower.shape = lb
	lower.position = Vector3(0.0, 0.17, 0.0)
	add_child(lower)
	var cabin := CollisionShape3D.new()
	var cb := BoxShape3D.new()
	cb.size = Vector3(1.4, 0.42, 2.0)
	cabin.shape = cb
	cabin.position = Vector3(0.0, 0.62, 0.25)
	add_child(cabin)


func _build_wheels() -> void:
	var half_w: float = track_width * 0.5
	var half_l: float = wheelbase * 0.5
	var spec: Array = [
		["WheelFL", true, true, Vector3(-half_w, mount_height, -half_l)],
		["WheelFR", true, false, Vector3(half_w, mount_height, -half_l)],
		["WheelRL", false, true, Vector3(-half_w, mount_height, half_l)],
		["WheelRR", false, false, Vector3(half_w, mount_height, half_l)],
	]
	for s: Array in spec:
		var w := CarWheel.new()
		w.name = s[0]
		w.is_front = s[1]
		w.is_left = s[2]
		w.position = s[3]
		match drivetrain:
			Drivetrain.RWD: w.is_driven = not w.is_front
			Drivetrain.FWD: w.is_driven = w.is_front
			_: w.is_driven = true
		add_child(w)
		w.setup(self, wheel_radius, rest_length, CarBodyVisual.make_wheel(wheel_radius, w.is_left))
		wheels.append(w)


func _physics_process(delta: float) -> void:
	_read_input(delta)
	var basis_now: Basis = global_basis
	var fwd: Vector3 = -basis_now.z
	var up: Vector3 = basis_now.y
	speed = linear_velocity.dot(fwd)
	_update_gearbox(delta)
	_update_drift(delta, up)

	# suspension, with an anti-roll bar per axle
	var loads: Array[float] = []
	for w: CarWheel in wheels:
		loads.append(w.update_suspension(delta, spring_stiffness, damping_bump, damping_rebound))
	for axle: int in 2:
		var l: CarWheel = wheels[axle * 2]
		var r: CarWheel = wheels[axle * 2 + 1]
		var roll: float = (l.compression - r.compression) * anti_roll
		if l.grounded:
			loads[axle * 2] = maxf(loads[axle * 2] + roll, 0.0)
		if r.grounded:
			loads[axle * 2 + 1] = maxf(loads[axle * 2 + 1] - roll, 0.0)

	var drive_total: float = _engine_force()
	var driven_count: int = 0
	for w: CarWheel in wheels:
		if w.is_driven and w.grounded:
			driven_count += 1

	var any_grounded: bool = false
	for i: int in wheels.size():
		var w: CarWheel = wheels[i]
		w.tire_load = loads[i]
		w.steer_angle = _steer if w.is_front else 0.0
		if not w.grounded:
			w.slip_lateral = 0.0
			w.slip_longitudinal = 0.0
			continue
		any_grounded = true
		var point: Vector3 = w.contact_point
		apply_force(up * w.tire_load, point - global_position)
		_apply_tire(w, delta, drive_total / maxf(driven_count, 1) if w.is_driven else 0.0, up)

	# aero and rolling resistance
	var v: Vector3 = linear_velocity
	apply_central_force(-v * v.length() * drag_coefficient - v * rolling_resistance)
	if any_grounded:
		apply_central_force(-up * downforce * v.length_squared())
		_stability(up, fwd)
		if _air_time > 0.35:
			landed.emit(clampf(_fall_speed / 12.0, 0.0, 1.0))
		_air_time = 0.0
	else:
		_air_time += delta
		_fall_speed = maxf(-linear_velocity.y, 0.0)
	for w: CarWheel in wheels:
		w.update_visual(delta)
	_auto_reset(delta)


func _read_input(delta: float) -> void:
	var accel: float = Input.get_action_strength("accelerate")
	var brk: float = Input.get_action_strength("brake")
	handbrake = Input.is_action_pressed("handbrake")
	steer_input = Input.get_axis("steer_right", "steer_left")
	# brake button selects reverse when the car is (almost) stopped
	if gear == -1:
		throttle = brk
		brake = accel
		if accel > 0.1 and speed > -1.0:
			gear = 1
			gear_changed.emit(gear)
	else:
		throttle = accel
		brake = brk
		if brk > 0.1 and accel < 0.1 and absf(speed) < 0.8:
			gear = -1
			gear_changed.emit(gear)
	if Input.is_action_just_pressed("reset_car"):
		reset_car()
	# speed-sensitive steering, with a little help to countersteer while sliding
	var kmh: float = absf(speed) * 3.6
	var max_angle: float = deg_to_rad(lerpf(max_steer_deg, high_speed_steer_deg, clampf(kmh / steer_falloff_kmh, 0.0, 1.0)))
	var target: float = steer_input * max_angle
	var lat: float = linear_velocity.dot(global_basis.x)
	if absf(speed) > 3.0 and (absf(steer_input) < 0.1 or drifting):
		var slip_angle: float = atan2(lat, absf(speed))
		target += clampf(slip_angle, -max_angle, max_angle) * countersteer_assist
	_steer = move_toward(_steer, target, steer_speed * delta)


func _update_gearbox(delta: float) -> void:
	var ratio: float = _current_ratio()
	var wheel_rpm: float = absf(speed) / (TAU * wheel_radius) * 60.0
	var target_rpm: float = maxf(idle_rpm, wheel_rpm * ratio * final_drive)
	if throttle > 0.05 and not _driven_grounded():
		target_rpm = lerpf(rpm, redline_rpm, 0.5)
	rpm = lerpf(rpm, minf(target_rpm, redline_rpm + 200.0), 1.0 - exp(-14.0 * delta))
	if _shift_timer > 0.0:
		_shift_timer -= delta
		return
	if gear >= 1:
		if rpm > shift_up_rpm and gear < gear_ratios.size() and throttle > 0.1:
			_shift(gear + 1)
		elif gear > 1 and rpm < shift_down_rpm:
			_shift(gear - 1)


func _shift(new_gear: int) -> void:
	gear = new_gear
	_shift_timer = shift_time
	gear_changed.emit(gear)


func _current_ratio() -> float:
	if gear == -1:
		return reverse_ratio
	if gear < 1:
		return 0.0
	return gear_ratios[gear - 1]


func _driven_grounded() -> bool:
	for w: CarWheel in wheels:
		if w.is_driven and w.grounded:
			return true
	return false


## Total drive force at the tires (newtons, positive pushes the car forward).
func _engine_force() -> float:
	if _shift_timer > 0.0 or gear == 0:
		return 0.0
	var dir: float = -1.0 if gear == -1 else 1.0
	if throttle < 0.02:
		return -signf(speed) * engine_braking * clampf(absf(speed), 0.0, 1.0)
	if rpm >= redline_rpm:
		return 0.0
	var torque: float = max_torque * torque_curve.sample_baked(clampf(rpm / redline_rpm, 0.0, 1.0)) * throttle
	return dir * torque * _current_ratio() * final_drive * drivetrain_efficiency / wheel_radius


func _apply_tire(w: CarWheel, delta: float, drive: float, up: Vector3) -> void:
	var b: Basis = global_basis
	var wheel_fwd: Vector3 = (-b.z).rotated(up, w.steer_angle)
	var wheel_right: Vector3 = wheel_fwd.cross(up).normalized()
	var r: Vector3 = w.contact_point - global_position
	var v: Vector3 = linear_velocity + angular_velocity.cross(r)
	var v_long: float = v.dot(wheel_fwd)
	var v_lat: float = v.dot(wheel_right)
	w.forward_speed = v_long
	w.slip_lateral = v_lat

	var mu: float = (front_grip if w.is_front else rear_grip) * float(surface_grip.get(String(w.surface), 1.0))
	if not w.is_front:
		if handbrake:
			mu *= handbrake_rear_grip
		elif drivetrain != Drivetrain.FWD:
			var sliding: float = clampf((absf(atan2(v_lat, maxf(absf(v_long), 1.0))) - deg_to_rad(peak_slip_deg)) / 0.3, 0.0, 1.0)
			var boost: float = drift_oversteer_boost if drifting else 1.0
			# past the drift angle limit the rear finds its grip again (assist), so the slide holds
			var hold: float = clampf((_beta - deg_to_rad(drift_max_angle_deg)) / deg_to_rad(10.0), 0.0, 1.0) if drifting else 0.0
			mu *= 1.0 - clampf(power_oversteer * boost, 0.0, 0.9) * throttle * sliding * (1.0 - hold)
	var max_force: float = mu * w.tire_load

	# lateral: slip-angle curve, rising to a peak, then falling to slide_grip
	var f_lat: float
	if absf(v_long) < 2.0:
		# at low speed just kill the sideways motion (no jitter when parked)
		f_lat = -v_lat * mass * 0.25 / delta / wheels.size()
		f_lat = clampf(f_lat, -max_force, max_force)
	else:
		var slip: float = atan2(v_lat, absf(v_long))
		var a: float = absf(slip) / deg_to_rad(peak_slip_deg)
		var shape: float = a * (2.0 - a) if a < 1.0 else lerpf(1.0, slide_grip, clampf((a - 1.0) / 3.0, 0.0, 1.0))
		f_lat = -signf(slip) * shape * max_force

	# longitudinal: drive, brakes, handbrake
	var f_long: float = drive
	var stop: float = clampf(absf(v_long) / 1.5, 0.0, 1.0)
	var brake_share: float = brake_bias_front if w.is_front else 1.0 - brake_bias_front
	f_long -= signf(v_long) * brake * brake_force * brake_share * 0.5 * stop
	if handbrake and not w.is_front:
		f_long -= signf(v_long) * handbrake_force * 0.5 * stop
	if traction_control and w.is_driven and throttle > 0.0:
		f_long = clampf(f_long, -max_force * 0.92, max_force * 0.92)

	# grip circle: the tire cannot push harder than mu * load in total
	var total: float = Vector2(f_long, f_lat).length()
	w.slip_longitudinal = 0.0
	if total > max_force and total > 0.0:
		w.slip_longitudinal = clampf((total - max_force) / maxf(max_force, 1.0), 0.0, 1.0)
		var k: float = max_force / total
		f_long *= k
		f_lat *= k
	apply_force(wheel_fwd * f_long + wheel_right * f_lat, r)


func _update_drift(delta: float, up: Vector3) -> void:
	var lat: float = linear_velocity.dot(global_basis.x)
	var beta: float = absf(atan2(lat, maxf(absf(speed), 1.0)))
	_beta = beta
	if Input.is_action_just_pressed("handbrake") and speed * 3.6 > drift_min_kmh and absf(steer_input) > 0.2:
		drifting = true
		_drift_time = 0.0
		# kick the tail out: an angular impulse that adds drift_kick rad/s of yaw
		var yaw_inertia: float = mass * (wheelbase * wheelbase + track_width * track_width) / 6.0
		apply_torque_impulse(up * signf(steer_input) * drift_kick * yaw_inertia)
	if drifting:
		_drift_time += delta
		# drift assist: hold the angle instead of spinning
		var over: float = clampf((beta - deg_to_rad(drift_max_angle_deg)) / deg_to_rad(15.0), 0.0, 1.0)
		if over > 0.0:
			apply_torque(-up * angular_velocity.dot(up) * mass * drift_assist * over * 4.0)
		var settled: bool = _drift_time > 0.4 and beta < deg_to_rad(peak_slip_deg * 1.2)
		if settled or speed * 3.6 < drift_min_kmh * 0.5:
			drifting = false


## Stability control: damps yaw when the car slides further than it should,
## unless the driver is drifting on purpose with the handbrake.
func _stability(up: Vector3, fwd: Vector3) -> void:
	if not stability_control or handbrake or drifting or absf(speed) < 5.0:
		return
	var lat: float = linear_velocity.dot(global_basis.x)
	var beta: float = absf(atan2(lat, absf(speed)))
	var excess: float = clampf((beta - deg_to_rad(12.0)) / deg_to_rad(25.0), 0.0, 1.0)
	if excess <= 0.0:
		return
	var yaw_rate: float = angular_velocity.dot(up)
	apply_torque(-up * yaw_rate * mass * stability_strength * excess * 2.0)


func _auto_reset(delta: float) -> void:
	if global_basis.y.y < 0.3 and linear_velocity.length() < 2.0:
		_flipped_time += delta
		if _flipped_time > 2.5:
			reset_car()
	else:
		_flipped_time = 0.0


func reset_car() -> void:
	var yaw: float = global_rotation.y
	global_transform = Transform3D(Basis(Vector3.UP, yaw), global_position + Vector3.UP * 1.5)
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	_flipped_time = 0.0
	reset_physics_interpolation()
	gear = 1
	gear_changed.emit(gear)
	car_reset.emit()


func speed_kmh() -> float:
	return absf(speed) * 3.6
