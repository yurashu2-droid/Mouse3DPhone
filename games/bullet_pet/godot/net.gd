extends Node

signal state_received(state: Dictionary)
signal config_received(config: Dictionary)
signal notice(message: String)

var port: int = 8767
var code: String = ""
var joined: bool = false
var axis: float = 0.0
var tilt_x: float = 0.0
var tilt_y: float = 0.0
var latest: Dictionary = {}
var config: Dictionary = {}
var _client: String = "godot-" + str(Time.get_unix_time_from_system()) + "-" + str(randi())
var _seq: int = 0
var _sse: HTTPClient = HTTPClient.new()
var _requested: bool = false
var _buffer: String = ""
var _retry_at: float = 0.0
var _last_state_at: float = 0.0
var _post: HTTPRequest
var _config_request: HTTPRequest
var _reset_request: HTTPRequest
var _post_busy: bool = false
var _post_action: String = "none"
var _pending: String = "none"
var _epoch: int = 0
var _post_epoch: int = 0
var _input_timer: float = 0.0
var _config_retry: float = 0.0

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			port = clampi(int(arg.trim_prefix("--port=")), 1, 65535)
	_post = HTTPRequest.new()
	_post.timeout = 2.0
	add_child(_post)
	_post.request_completed.connect(_input_done)
	_config_request = HTTPRequest.new()
	_config_request.timeout = 3.0
	add_child(_config_request)
	_config_request.request_completed.connect(_config_done)
	_reset_request = HTTPRequest.new()
	_reset_request.timeout = 3.0
	add_child(_reset_request)
	_reset_request.request_completed.connect(_reset_done)
	load_config()

func _url(path: String) -> String:
	return "http://127.0.0.1:%d%s" % [port, path]

func load_config() -> void:
	_config_retry = Time.get_ticks_msec() / 1000.0 + 3.0
	_config_request.request(_url("/api/config"))

func _config_done(result: int, status: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or status != 200:
		notice.emit("サーバーを待っています。Start-Bullet-Pet-3D.cmdから起動してください。")
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	if not data is Dictionary or not data.has("code"):
		return
	config = data
	code = str(config["code"])
	config_received.emit(config)
	_connect_stream()

func _connect_stream() -> void:
	_sse.close()
	_buffer = ""
	_requested = false
	_sse.connect_to_host("127.0.0.1", port)
	_retry_at = Time.get_ticks_msec()/1000.0 + 2.0

func _process(delta: float) -> void:
	var now: float = Time.get_ticks_msec()/1000.0
	if code.is_empty():
		if now >= _config_retry:
			load_config()
		return
	_sse.poll()
	var status: int = _sse.get_status()
	if status == HTTPClient.STATUS_CONNECTED and not _requested:
		_requested = true
		_sse.request(HTTPClient.METHOD_GET, "/api/events?code="+code, PackedStringArray(["Accept: text/event-stream"]))
	elif status == HTTPClient.STATUS_BODY:
		if _sse.get_response_code() != 200:
			_sse.close()
			code = ""
			joined = false
			_config_retry = now + 1.0
			return
		var chunk: PackedByteArray = _sse.read_response_body_chunk()
		if not chunk.is_empty():
			_buffer += chunk.get_string_from_utf8()
			_parse_stream()
	elif status in [HTTPClient.STATUS_DISCONNECTED, HTTPClient.STATUS_CANT_CONNECT, HTTPClient.STATUS_CONNECTION_ERROR, HTTPClient.STATUS_CANT_RESOLVE]:
		if now > _retry_at:
			_connect_stream()
	if joined and _last_state_at > 0 and now-_last_state_at > 2:
		release()
		notice.emit("通信が途切れました。接続後、PCデモ参加で再開できます。")
	_input_timer += delta
	if _input_timer >= 1.0/30.0:
		_input_timer = 0.0
		if joined:
			_send_input()

func _parse_stream() -> void:
	while true:
		var end: int = _buffer.find("\n\n")
		if end < 0:
			break
		var event: String = _buffer.substr(0, end)
		_buffer = _buffer.substr(end+2)
		for line in event.split("\n"):
			if line.begins_with("data: "):
				var state = JSON.parse_string(line.substr(6))
				if state is Dictionary and state.has("phase"):
					latest = state
					_last_state_at = Time.get_ticks_msec()/1000.0
					if joined and state.get("phase", "") == "paused":
						joined = false
					state_received.emit(state)
	if _buffer.length() > 131072:
		_connect_stream()

func join_demo() -> void:
	if code.is_empty() or _post_busy:
		return
	_pending = "join"
	_send_input()

func fire() -> void:
	if joined:
		_pending = "fire"

func _payload(action: String, active: bool = true) -> String:
	_seq += 1
	return JSON.stringify({"code":code,"client":_client,"seq":_seq,"x":axis,
		"tiltX":tilt_x,"tiltY":tilt_y,"active":active,"action":action,"mode":"demo"})

func _send_input() -> void:
	if _post_busy:
		return
	_post_action = _pending
	_pending = "none"
	_post_epoch = _epoch
	_post_busy = true
	var result: int = _post.request(_url("/api/input"), PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, _payload(_post_action))
	if result != OK:
		_post_busy = false
		joined = false

func _input_done(result: int, status: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_post_busy = false
	if _post_epoch != _epoch:
		return
	if result == HTTPRequest.RESULT_SUCCESS and status == 200:
		if _post_action == "join":
			joined = true
			notice.emit("PCデモ：マウスで受け口、矢印キーで容器、SPACEで発射")
	else:
		joined = false
		var data = JSON.parse_string(body.get_string_from_utf8())
		var message: String = "通信を確認して、もう一度参加してください。"
		if data is Dictionary:
			message = str(data.get("error", message))
		notice.emit(message)

func release() -> void:
	var was_active: bool = joined or _post_busy
	joined = false
	_pending = "none"
	_epoch += 1
	if not was_active or code.is_empty():
		return
	# Separate request lets an in-flight action finish without silently rejoining.
	var request: HTTPRequest = HTTPRequest.new()
	request.timeout = 1.0
	add_child(request)
	request.request_completed.connect(func(_a, _b, _c, _d): request.queue_free())
	request.request(_url("/api/input"), PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, _payload("none", false))

func reset_game() -> void:
	release()
	_reset_request.request(_url("/api/reset"), PackedStringArray(["Content-Type: application/json"]), HTTPClient.METHOD_POST, JSON.stringify({"code":code}))

func _reset_done(_result: int, status: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if status == 200:
		notice.emit("新しい実験を用意しました。スマホかPCデモで参加してください。")

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and is_node_ready():
		release()
