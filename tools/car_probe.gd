extends SceneTree
## Headless driving check: godot --headless --path . --script res://tools/car_probe.gd
## Loads the test track, lets the car settle, accelerates, brakes, turns and drifts, and
## prints what happened. Exits 1 if the car flips, sinks, flies off or never moves.

func _initialize() -> void:
	var scene: Node = load("res://scenes/levels/test_track.tscn").instantiate()
	root.add_child(scene)
	var car: CarController = scene.get_node("Car")
	var fail: Array[String] = []
	await _wait(1.5)
	var settle_y: float = car.global_position.y
	print("settled y=%.3f grounded=%s" % [settle_y, str(car.wheels.map(func(w): return w.grounded))])
	if settle_y < 0.1 or settle_y > 0.9:
		fail.append("bad ride height")
	Input.action_press("accelerate")
	await _wait(4.0)
	var v4: float = car.speed_kmh()
	print("after 4 s throttle: %.1f km/h gear %d rpm %d" % [v4, car.gear, car.rpm])
	await _wait(6.0)
	print("after 10 s throttle: %.1f km/h gear %d" % [car.speed_kmh(), car.gear])
	if v4 < 40.0:
		fail.append("too slow")
	Input.action_release("accelerate")
	Input.action_press("brake")
	await _wait(2.0)
	print("after 2 s braking: %.1f km/h" % car.speed_kmh())
	Input.action_release("brake")
	Input.action_press("accelerate")
	Input.action_press("steer_left")
	await _wait(3.0)
	print("turning: %.1f km/h yaw %.1f deg up.y %.2f" % [car.speed_kmh(), rad_to_deg(car.global_rotation.y), car.global_basis.y.y])
	Input.action_release("steer_left")
	await _wait(5.0)                            # straighten up and build speed
	# a fast corner without the handbrake must grip, not slide
	print("fast corner at %.1f km/h" % car.speed_kmh())
	Input.action_press("steer_right")
	var corner_peak: float = 0.0
	for i: int in 16:
		await _wait(0.125)
		corner_peak = maxf(corner_peak, rad_to_deg(absf(atan2(car.linear_velocity.dot(car.global_basis.x), absf(car.speed)))))
	Input.action_release("steer_right")
	print("fast corner: peak body angle %.0f deg (should stay small), %.1f km/h" % [corner_peak, car.speed_kmh()])
	if corner_peak > 14.0:
		fail.append("slides in a normal corner")
	await _wait(2.0)
	# drift test on the big pad: start fresh, build speed in a straight line
	car.global_transform = Transform3D(Basis.IDENTITY, Vector3(106.0, 1.0, 20.0))
	car.linear_velocity = Vector3.ZERO
	car.angular_velocity = Vector3.ZERO
	car.reset_physics_interpolation()
	Input.action_release("steer_left")
	Input.action_release("steer_right")
	await _wait(4.5)
	print("before drift: %.1f km/h" % car.speed_kmh())
	Input.action_press("steer_left")
	Input.action_press("handbrake")
	await _wait(0.25)
	Input.action_release("handbrake")
	var peak: float = 0.0
	for i: int in 12:
		await _wait(0.125)
		print("  t%.2f v%.1f beta%.0f yaw%.2f drift=%s gear%d thr%.1f hb=%s" % [i * 0.125, car.speed_kmh(), rad_to_deg(atan2(car.linear_velocity.dot(car.global_basis.x), absf(car.speed))), car.angular_velocity.y, str(car.drifting), car.gear, car.throttle, str(car.handbrake)])
		peak = maxf(peak, rad_to_deg(absf(atan2(car.linear_velocity.dot(car.global_basis.x), absf(car.speed)))))
	print("drift: peak body angle %.0f deg, drifting=%s, %.1f km/h" % [peak, str(car.drifting), car.speed_kmh()])
	Input.action_release("steer_left")
	await _wait(2.0)
	print("after drift: angle %.0f deg, drifting=%s, up.y %.2f" % [rad_to_deg(absf(atan2(car.linear_velocity.dot(car.global_basis.x), absf(car.speed)))), str(car.drifting), car.global_basis.y.y])
	if peak < 12.0:
		fail.append("drift does not start")
	Input.action_release("accelerate")
	await _wait(3.0)
	print("end: %.1f km/h up.y %.2f pos %s" % [car.speed_kmh(), car.global_basis.y.y, str(car.global_position.snapped(Vector3.ONE * 0.1))])
	if car.global_basis.y.y < 0.8:
		fail.append("flipped")
	if car.global_position.y < -1.0 or car.global_position.y > 5.0:
		fail.append("left the ground")
	print("RESULT " + ("ok" if fail.is_empty() else "FAIL: " + ", ".join(fail)))
	quit(1 if not fail.is_empty() else 0)


func _wait(seconds: float) -> void:
	for i: int in int(seconds * Engine.physics_ticks_per_second):
		await physics_frame
