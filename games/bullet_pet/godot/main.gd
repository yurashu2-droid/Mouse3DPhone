extends Node3D

const ArenaScript = preload("res://arena.gd")
const NetworkScript = preload("res://net.gd")
const MINT = Color("75efda")
const CORAL = Color("ff8e8b")
const INK = Color("07151f")
const IVORY = Color("e8f4ee")

var arena: Node3D
var link: Node
var _phase: Label
var _instruction: Label
var _timer: Label
var _score: Label
var _hp: ProgressBar
var _hp_label: Label
var _life: Label
var _code: Label
var _address: Label
var _port_help: Label
var _status: Label
var _pocket: Label
var _join: Button
var _fire: Button
var _flash: ColorRect
var _state: Dictionary = {}
var _seen_fx: Dictionary = {}
var _sound_on: bool = true
var _sounds: Dictionary = {}
var _players: Array[AudioStreamPlayer] = []
var _player_index: int = 0
var _clock: float = 0.0
var _auto_joined: bool = false

func _ready() -> void:
	get_tree().auto_accept_quit = false
	arena = ArenaScript.new()
	add_child(arena)
	link = NetworkScript.new()
	_build_ui()
	link.state_received.connect(_on_state)
	link.config_received.connect(_on_config)
	link.notice.connect(func(message: String): _status.text = message)
	add_child(link)
	_build_audio()

func _label(text: String, size: int, color: Color = IVORY) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label

func _panel(color: Color = Color(0.025, 0.07, 0.09, .9)) -> PanelContainer:
	var p: PanelContainer = PanelContainer.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = Color(0.35, .75, .7, .25)
	style.set_border_width_all(1)
	style.set_corner_radius_all(14)
	style.content_margin_left = 24
	style.content_margin_right = 24
	style.content_margin_top = 20
	style.content_margin_bottom = 20
	p.add_theme_stylebox_override("panel", style)
	return p

func _button(text: String, action: Callable, accent: bool = false) -> Button:
	var button: Button = Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(0, 46)
	button.add_theme_font_size_override("font_size", 15)
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = MINT if accent else Color("16313b")
	style.set_corner_radius_all(7)
	button.add_theme_stylebox_override("normal", style)
	var hover: StyleBoxFlat = style.duplicate()
	hover.bg_color = style.bg_color.lightened(.16)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_color_override("font_color", INK if accent else IVORY)
	button.add_theme_color_override("font_hover_color", INK if accent else IVORY)
	button.pressed.connect(action)
	return button

func _build_ui() -> void:
	var layer: CanvasLayer = CanvasLayer.new()
	add_child(layer)
	var ui: Control = Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(ui)
	var font: SystemFont = SystemFont.new()
	font.font_names = PackedStringArray(["Yu Gothic UI", "Meiryo", "Arial"])
	var theme: Theme = Theme.new()
	theme.default_font = font
	ui.theme = theme
	var title: VBoxContainer = VBoxContainer.new()
	title.position = Vector2(48, 30)
	title.add_theme_constant_override("separation", 1)
	ui.add_child(title)
	title.add_child(_label("BULLET PET", 35))
	title.add_child(_label("弾を飼う   /   ORBITAL FOUNDRY", 12, MINT))
	var boss: VBoxContainer = VBoxContainer.new()
	boss.position = Vector2(410, 32)
	boss.size = Vector2(600, 65)
	ui.add_child(boss)
	_hp_label = _label("THE KEEPER     /     REACTOR INTEGRITY 100", 12, CORAL)
	boss.add_child(_hp_label)
	_hp = ProgressBar.new()
	_hp.custom_minimum_size = Vector2(600, 7)
	_hp.show_percentage = false
	_hp.value = 100
	var background: StyleBoxFlat = StyleBoxFlat.new()
	background.bg_color = Color("1d3541")
	background.set_corner_radius_all(4)
	_hp.add_theme_stylebox_override("background", background)
	var fill: StyleBoxFlat = background.duplicate()
	fill.bg_color = CORAL
	_hp.add_theme_stylebox_override("fill", fill)
	boss.add_child(_hp)
	var right: PanelContainer = _panel()
	right.position = Vector2(1080, 30)
	right.size = Vector2(312, 0)
	ui.add_child(right)
	var column: VBoxContainer = VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	right.add_child(column)
	column.add_child(_label("YOUR POCKET / スマホを接続", 12, MINT))
	column.add_child(_label("この光を、\n手の中で育てる。", 25))
	_code = _label("------", 38, MINT)
	column.add_child(_code)
	_address = _label("PCのサーバーに接続中…", 13)
	_address.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_address.custom_minimum_size.x = 264
	column.add_child(_address)
	_port_help = _label("iPhoneアプリのゲーム画面から\nIPv4・ポート・コードを入力。", 13, Color("a4babd"))
	column.add_child(_port_help)
	column.add_child(_button("接続ページを開く", func(): OS.shell_open("http://127.0.0.1:%d/" % link.port)))
	_join = _button("PCだけで遊ぶ", func(): link.join_demo(), true)
	column.add_child(_join)
	_fire = _button("送りかえす  /  SPACE", func(): link.fire())
	column.add_child(_fire)
	column.add_child(_button("停止・持ち直す", func(): link.release()))
	column.add_child(_button("最初から", func(): link.reset_game()))
	column.add_child(_button("音を切り替える", func(): _sound_on = not _sound_on))
	_status = _label("スマホかPCデモで参加すると開始します。", 12, Color("a4babd"))
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_status)
	_pocket = _label("POCKET / 0 個", 16, MINT)
	column.add_child(_pocket)
	var bottom: PanelContainer = _panel(Color(.02, .055, .075, .92))
	bottom.position = Vector2(48, 764)
	bottom.size = Vector2(980, 105)
	ui.add_child(bottom)
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 32)
	bottom.add_child(row)
	var left: VBoxContainer = VBoxContainer.new()
	left.custom_minimum_size.x = 590
	row.add_child(left)
	_phase = _label("READY / 接続を待っています", 23, MINT)
	left.add_child(_phase)
	_instruction = _label("手元に入れた弾は、傾けて同じ色を合わせよう。", 13)
	left.add_child(_instruction)
	var numbers: VBoxContainer = VBoxContainer.new()
	row.add_child(numbers)
	_timer = _label("120 s", 24)
	_life = _label("STABILITY  5 / 5", 12, CORAL)
	_score = _label("SCORE  0000", 12, MINT)
	numbers.add_child(_timer)
	numbers.add_child(_life)
	numbers.add_child(_score)
	_flash = ColorRect.new()
	_flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_flash.color = Color(1, .25, .3, 0)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(_flash)

func _on_config(config: Dictionary) -> void:
	_code.text = str(config.get("code", "------"))
	var urls: Array = config.get("urls", [])
	var ips: PackedStringArray = []
	for url in urls:
		ips.append(str(url).trim_prefix("http://").split(":")[0])
	_address.text = "PC IPv4  " + ", ".join(ips) + "\nPORT  " + str(link.port)
	_port_help.text = "iPhoneアプリのゲーム画面から\nIPv4・%d・コードを入力。" % link.port

func _on_state(state: Dictionary) -> void:
	_state = state
	arena.apply_snapshot(state)
	var boss: Dictionary = state.get("boss", {})
	_hp.value = float(boss.get("hp", 100))
	_hp_label.text = "THE KEEPER     /     REACTOR INTEGRITY %d" % int(_hp.value)
	_timer.text = "%03d s" % int(ceil(float(state.get("timeLeft", 120))))
	_score.text = "SCORE  %04d" % int(state.get("score", 0))
	_life.text = "STABILITY  %d / 5" % int(state.get("lives", 5))
	var phase: String = str(state.get("phase", "waiting"))
	var phases: Dictionary = {
		"waiting":["READY / 接続を待っています", "スマホで参加、または右のPCデモで開始。"],
		"catch":["01  CATCH / 受けとめる", "弾の通り道に受け口を合わせ、手元の器へ。"],
		"grow":["02  GROW / 育てる", "攻撃は停止中。同色・同レベルを合体、異色は離す。"],
		"fire":["03  RETURN / 送りかえす", "敵へ狙いを合わせ、スマホの発射かSPACE。"],
		"paused":["PAUSED / ひとやすみ", "再開はスマホの参加、または右のPCデモから。"],
		"won":["REACTOR CLEARED / 実験成功", "あなたが育てた光が、敵をたおした。"],
		"lost":["EXPERIMENT OVER / 実験終了", "最初から、違う組み合わせでもう一度。"]}
	var words: Array = phases.get(phase, phases["waiting"])
	_phase.text = str(words[0])
	if phase in ["catch", "grow", "fire"]:
		_phase.text += "   %ds" % int(ceil(float(state.get("phaseLeft", 0))))
	_instruction.text = str(words[1])
	_fire.disabled = not link.joined or phase not in ["grow", "fire"]
	_join.text = "PCデモ操作中" if link.joined else "PCだけで遊ぶ"
	_join.disabled = state.get("controller") == "phone"
	var balls: Array = state.get("balls", [])
	var level: int = 0
	for ball in balls:
		level = maxi(level, int(ball.get("level", 0)))
	_pocket.text = "POCKET  %d / 6     MAX LV %d" % [balls.size(), level]
	for fx in state.get("fx", []):
		var identifier: int = int(fx.get("id", 0))
		if not _seen_fx.has(identifier):
			_seen_fx[identifier] = true
			_play_sound(str(fx.get("type", "capture")))
			if fx.get("type") == "clash":
				_flash.color.a = .17
	if _seen_fx.size() > 200:
		_seen_fx.clear()

func _process(delta: float) -> void:
	_clock += delta
	if "--smoke-demo" in OS.get_cmdline_user_args() and not _auto_joined and _clock > 1.0 and not link.code.is_empty():
		_auto_joined = true
		link.join_demo()
	if is_instance_valid(_flash):
		_flash.color.a = move_toward(_flash.color.a, 0, delta*.7)
	if not is_instance_valid(link) or not link.joined:
		return
	var x: float = float(Input.is_physical_key_pressed(KEY_RIGHT) or Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_LEFT) or Input.is_physical_key_pressed(KEY_A))
	var y: float = float(Input.is_physical_key_pressed(KEY_DOWN) or Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_UP) or Input.is_physical_key_pressed(KEY_W))
	link.axis = clampf(link.axis + x*delta*1.2, -1, 1)
	link.tilt_x = x
	link.tilt_y = y
	# Smoke mode checks the actual renderer + HTTP input, never used in normal play.
	if "--smoke-demo" in OS.get_cmdline_user_args() and _clock > 1.0:
		link.axis = sin(_clock*.7)*.7
		link.tilt_x = sin(_clock)*.45
		link.tilt_y = .4
		if _state.get("phase") in ["grow", "fire"]:
			link.axis = clampf((float(_state.get("boss", {}).get("x", .5))-.5)/.4, -1, 1)
			if fmod(_clock, .6) < .05:
				link.fire()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			link.fire()
		elif event.keycode == KEY_ESCAPE:
			link.release()
	if event is InputEventMouseMotion and link.joined:
		var width: float = get_viewport().get_visible_rect().size.x
		if event.position.x < width*.72:
			link.axis = clampf((event.position.x/width/.72)*2-1, -1, 1)

func _build_audio() -> void:
	for kind in ["capture", "merge", "clash", "hit", "miss"]:
		var duration: float = .16 if kind == "capture" else .32
		var samples: int = int(22050*duration)
		var data: PackedByteArray = PackedByteArray()
		data.resize(samples*2)
		for i in samples:
			var t: float = float(i)/22050.0
			var progress: float = t/duration
			var frequency: float = 650.0
			if kind == "merge": frequency = 300.0 + progress*1100.0
			if kind == "hit": frequency = 130.0-progress*85.0
			if kind == "clash": frequency = 190.0-progress*120.0
			if kind == "miss": frequency = 170.0
			var value: float = sin(TAU*frequency*t)*pow(1-progress, 2)*minf(1, t*180)*.18
			if kind in ["clash", "hit"]:
				value += randf_range(-1, 1)*pow(1-progress, 4)*.1
			data.encode_s16(i*2, int(value*32767))
		var sound: AudioStreamWAV = AudioStreamWAV.new()
		sound.format = AudioStreamWAV.FORMAT_16_BITS
		sound.mix_rate = 22050
		sound.data = data
		_sounds[kind] = sound
	for i in 5:
		var player: AudioStreamPlayer = AudioStreamPlayer.new()
		player.volume_db = -9
		add_child(player)
		_players.append(player)

func _play_sound(kind: String) -> void:
	if not _sound_on or not _sounds.has(kind) or _players.is_empty():
		return
	var player: AudioStreamPlayer = _players[_player_index % _players.size()]
	_player_index += 1
	player.stream = _sounds[kind]
	player.play()

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if is_instance_valid(link):
			link.release()
		get_tree().quit()
