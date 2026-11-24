extends Node
## Global game state. Also registers the default controls, so the project works
## without editing the Input Map by hand (they can still be changed there).

const DEFAULT_KEYS: Dictionary = {
	"accelerate": [KEY_W, KEY_UP],
	"brake": [KEY_S, KEY_DOWN],
	"steer_left": [KEY_A, KEY_LEFT],
	"steer_right": [KEY_D, KEY_RIGHT],
	"handbrake": [KEY_SPACE],
	"camera_next": [KEY_C],
	"reset_car": [KEY_R],
	"fly_up": [KEY_E],
	"fly_down": [KEY_Q],
	"fly_fast": [KEY_SHIFT],
}


func _ready() -> void:
	_register_default_input()


func _register_default_input() -> void:
	for action: String in DEFAULT_KEYS:
		if InputMap.has_action(action):
			continue
		InputMap.add_action(action, 0.2)
		for key: Key in DEFAULT_KEYS[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			InputMap.action_add_event(action, ev)
