class_name CarHud
extends CanvasLayer
## Horizon-style driving HUD, anchored to the bottom-right corner (it stays in the corner at
## any aspect ratio): big speed number, km/h, gear badge and an RPM bar that turns red near
## the redline. The gear updates from the car's gear_changed signal; speed and RPM are
## continuous gauges, so they are read once per frame. A controls hint fades out after a while.

@export var car_path: NodePath
@export var accent: Color = Color(1.0, 0.36, 0.62)          ## festival pink
@export var hint_seconds: float = 8.0

var _car: CarController
var _speed: Label
var _gear: Label
var _rpm_fill: ColorRect
var _rpm_back: ColorRect
var _shown_speed: float = 0.0


func _ready() -> void:
	_car = get_node(car_path) as CarController
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	var box := VBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	box.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	box.grow_vertical = Control.GROW_DIRECTION_BEGIN
	box.offset_right = -56.0
	box.offset_bottom = -44.0
	box.alignment = BoxContainer.ALIGNMENT_END
	box.add_theme_constant_override("separation", 2)
	root.add_child(box)

	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 14)
	box.add_child(row)
	var gear_panel := PanelContainer.new()
	var gs := StyleBoxFlat.new()
	gs.bg_color = Color(0.05, 0.06, 0.08, 0.72)
	gs.border_color = accent
	gs.set_border_width_all(3)
	gs.set_corner_radius_all(40)
	gs.content_margin_left = 18.0
	gs.content_margin_right = 18.0
	gear_panel.add_theme_stylebox_override("panel", gs)
	gear_panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_gear = _label("1", 40)
	gear_panel.add_child(_gear)
	row.add_child(gear_panel)
	_speed = _label("0", 96)
	_speed.custom_minimum_size = Vector2(190, 0)
	_speed.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(_speed)
	var unit := _label("KM/H", 22)
	unit.size_flags_vertical = Control.SIZE_SHRINK_END
	unit.modulate = Color(1, 1, 1, 0.8)
	row.add_child(unit)

	_rpm_back = ColorRect.new()
	_rpm_back.color = Color(1, 1, 1, 0.16)
	_rpm_back.custom_minimum_size = Vector2(340, 8)
	_rpm_back.size_flags_horizontal = Control.SIZE_SHRINK_END
	box.add_child(_rpm_back)
	_rpm_fill = ColorRect.new()
	_rpm_fill.color = accent
	_rpm_fill.size = Vector2(0, 8)
	_rpm_back.add_child(_rpm_fill)

	var hint := _label("W/S acelerar y frenar · A/D girar · Espacio freno de mano · C cámara · R reiniciar", 20)
	hint.set_anchors_preset(Control.PRESET_TOP_LEFT)
	hint.position = Vector2(40, 32)
	root.add_child(hint)
	var tw := hint.create_tween()
	tw.tween_interval(hint_seconds)
	tw.tween_property(hint, "modulate:a", 0.0, 0.6).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)

	_car.gear_changed.connect(_on_gear_changed)
	_on_gear_changed(_car.gear)                    # signals do not replay the initial state


func _label(text: String, size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", Color.WHITE)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.55))
	l.add_theme_constant_override("outline_size", maxi(4, size / 12))
	return l


func _on_gear_changed(g: int) -> void:
	_gear.text = "R" if g == -1 else ("N" if g == 0 else str(g))
	# little pop on every change, eased back to rest
	_gear.pivot_offset = _gear.size * 0.5
	_gear.scale = Vector2(1.25, 1.25)
	var tw := _gear.create_tween()
	tw.tween_property(_gear, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func _process(delta: float) -> void:
	_shown_speed = lerpf(_shown_speed, _car.speed_kmh(), 1.0 - exp(-12.0 * delta))
	_speed.text = str(int(round(_shown_speed)))
	var r: float = clampf((_car.rpm - _car.idle_rpm) / (_car.redline_rpm - _car.idle_rpm), 0.0, 1.0)
	_rpm_fill.size = Vector2(_rpm_back.size.x * r, _rpm_back.size.y)
	_rpm_fill.color = Color(1.0, 0.22, 0.2) if _car.rpm > _car.shift_up_rpm - 300.0 else accent
