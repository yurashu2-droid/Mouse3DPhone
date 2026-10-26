extends Node3D
## Orbital containment chamber. All geometry and light are procedural.
var state: Dictionary = {}
var entities: Dictionary = {}
var effects: Array[Dictionary] = []
var seen_fx: Dictionary = {}
var boss: Node3D
var receiver: Node3D
var core: MeshInstance3D
var gimbals: Array[Node3D] = []
var clock_time: float = 0.0
var boss_recoil: float = 0.0
var cyan := Color("47e5ed")
var coral := Color("ff735e")
var metal: StandardMaterial3D
var dark: StandardMaterial3D
var pale: StandardMaterial3D

func material(color: Color, metallic: float = 0.0, emission: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = 0.28 if metallic > 0.0 else 0.5
	if emission > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission
	return m

func mesh(parent: Node3D, geometry: Mesh, pos: Vector3, mat: Material) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	n.mesh = geometry
	n.material_override = mat
	n.position = pos
	parent.add_child(n)
	return n

func box(parent: Node3D, size: Vector3, pos: Vector3, mat: Material) -> MeshInstance3D:
	var shape := BoxMesh.new()
	shape.size = size
	return mesh(parent, shape, pos, mat)

func sphere(parent: Node3D, radius: float, pos: Vector3, mat: Material) -> MeshInstance3D:
	var shape := SphereMesh.new()
	shape.radius = radius
	shape.height = radius * 2.0
	shape.radial_segments = 24
	shape.rings = 12
	return mesh(parent, shape, pos, mat)

func ring(parent: Node3D, radius: float, thickness: float, pos: Vector3, mat: Material) -> MeshInstance3D:
	var shape := TorusMesh.new()
	shape.inner_radius = radius - thickness
	shape.outer_radius = radius + thickness
	shape.rings = 64
	shape.ring_segments = 12
	return mesh(parent, shape, pos, mat)

func cylinder(parent: Node3D, radius: float, height: float, pos: Vector3, mat: Material) -> MeshInstance3D:
	var shape := CylinderMesh.new()
	shape.top_radius = radius
	shape.bottom_radius = radius * 1.05
	shape.height = height
	shape.radial_segments = 64
	return mesh(parent, shape, pos, mat)

func _ready() -> void:
	metal = material(Color("40596a"), 0.82)
	dark = material(Color("101e2b"), 0.65)
	pale = material(Color("a9c9cb"), 0.72)
	var env := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("060d18")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("6d9db2")
	environment.ambient_light_energy = 0.48
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.glow_enabled = true
	environment.glow_intensity = 0.7
	environment.fog_enabled = true
	environment.fog_light_color = Color("0a1c30")
	environment.fog_density = 0.008
	env.environment = environment
	add_child(env)
	var camera := Camera3D.new()
	add_child(camera)
	camera.position = Vector3(0, 12.8, 18.8)
	camera.look_at(Vector3(0, 0, -1.5))
	camera.fov = 46
	camera.h_offset = 2.0
	camera.current = true
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-48, -28, 0)
	key.light_color = Color("c1e9ef")
	key.light_energy = 1.7
	key.shadow_enabled = true
	add_child(key)
	add_light(Vector3(-6, 5, -4), cyan, 12.0, 14.0)
	add_light(Vector3(6, 4, -7), coral, 9.0, 12.0)
	build_chamber()
	build_boss()
	build_receiver()

func add_light(pos: Vector3, color: Color, energy: float, radius: float) -> void:
	var light := OmniLight3D.new()
	light.position = pos
	light.light_color = color
	light.light_energy = energy
	light.omni_range = radius
	add_child(light)

func build_chamber() -> void:
	# Thick chamfer-like stacked deck, with an inset playing surface.
	box(self, Vector3(16.4, 0.5, 15.4), Vector3(0, -0.85, -1.5), dark)
	box(self, Vector3(15.7, 0.16, 14.7), Vector3(0, -0.52, -1.5), metal)
	box(self, Vector3(14.4, 0.12, 13.7), Vector3(0, -0.36, -1.5), material(Color("102936"), 0.55))
	var dim := material(Color("17606b"), 0.4, 0.8)
	for side in [-1.0, 1.0]:
		box(self, Vector3(0.38, 0.4, 14.4), Vector3(side * 7.6, -0.22, -1.5), pale)
		box(self, Vector3(0.06, 0.03, 13.8), Vector3(side * 7.32, 0.005, -1.5), material(cyan, 0.2, 2))
		for index in range(9):
			var z: float = -7.5 + index * 1.5
			box(self, Vector3(0.65, 0.12, 0.45), Vector3(side * 7.65, 0.08, z), dark)
			box(self, Vector3(0.32, 0.03, 0.06), Vector3(side * 7.65, 0.15, z), dim)
	for z in [-6.0, -3.0, 0.0, 3.0]:
		for x in [-4.8, 0.0, 4.8]:
			box(self, Vector3(0.018, 0.01, 1.1), Vector3(x, -0.285, z), dim)
			box(self, Vector3(0.5, 0.01, 0.018), Vector3(x, -0.28, z), dim)
	# Floating machinery in the dark beyond the chamber creates parallax and scale.
	for side in [-1.0, 1.0]:
		for i in range(4):
			var pos := Vector3(side * (10.0 + i * 0.5), 1.5 + i * 0.5, -8.0 + i * 4)
			cylinder(self, 0.65, 4.5, pos, dark)
			ring(self, 0.69, 0.035, pos + Vector3(0, 1.4, 0), dim)
			box(self, Vector3(0.08, 2.0, 0.08), pos + Vector3(-side * 0.67, 0, 0), dim)
	var dais := cylinder(self, 2.6, 0.35, Vector3(0, -0.12, -6.8), dark)
	ring(dais, 2.35, 0.025, Vector3(0, 0.21, 0), material(coral, 0.2, 1.5))

func build_boss() -> void:
	boss = Node3D.new()
	add_child(boss)
	boss.position = Vector3(0, 2.0, -6.8)
	var glow := material(coral, 0.3, 2.8)
	core = sphere(boss, 0.7, Vector3.ZERO, glow)
	# Gimbal planes frame a luminous heart without obscuring it.
	for i in range(3):
		var pivot := Node3D.new()
		boss.add_child(pivot)
		pivot.rotation_degrees = Vector3(25 + i * 52, i * 58, i * 22)
		ring(pivot, 1.05 + i * 0.22, 0.075, Vector3.ZERO, pale if i == 0 else metal)
		ring(pivot, 1.05 + i * 0.22, 0.018, Vector3(0, 0.07, 0), glow)
		gimbals.append(pivot)
	for i in range(8):
		var angle: float = i * TAU / 8
		var arm := Node3D.new()
		boss.add_child(arm)
		arm.rotation.z = angle
		var plate := box(arm, Vector3(0.57, 0.95, 0.48), Vector3(0, 1.7, 0), metal)
		plate.rotation.x = -0.2
		box(arm, Vector3(0.3, 0.6, 0.12), Vector3(0, 1.73, 0.3), pale)
		box(arm, Vector3(0.1, 0.32, 0.06), Vector3(0, 1.78, 0.38), glow)
		cylinder(arm, 0.13, 0.5, Vector3(0, 1.12, 0), dark)
	# Lower exhaust structure and subtle scanning eye.
	var eye := sphere(boss, 0.23, Vector3(0, 0, 0.8), material(Color("fff1db"), 0.0, 3))
	eye.scale = Vector3(1, 0.28, 0.5)

func build_receiver() -> void:
	receiver = Node3D.new()
	add_child(receiver)
	receiver.position = Vector3(0, 0.2, 4.0)
	box(receiver, Vector3(3.25, 0.22, 1.65), Vector3(0, 0, 0), pale)
	box(receiver, Vector3(2.95, 0.13, 1.4), Vector3(0, 0.15, 0), dark)
	box(receiver, Vector3(2.65, 0.04, 1.15), Vector3(0, 0.24, 0), material(Color("103945"), 0.55))
	for side in [-1.0, 1.0]:
		box(receiver, Vector3(0.13, 0.5, 1.6), Vector3(side * 1.53, 0.34, 0), metal)
		box(receiver, Vector3(0.055, 0.035, 1.3), Vector3(side * 1.53, 0.61, 0), material(cyan, 0.0, 2.0))
	box(receiver, Vector3(2.8, 0.2, 0.16), Vector3(0, 0.35, 0.76), metal)
	box(receiver, Vector3(1.3, 0.035, 0.05), Vector3(0, 0.48, 0.78), material(cyan, 0.0, 1.5))

func point(x: float, y: float) -> Vector3:
	return Vector3((x - 0.5) * 14.0, 0.65, remap(y, 0.14, 0.86, -7.0, 4.0))

func apply_snapshot(value: Dictionary) -> void:
	state = value
	var alive: Dictionary = {}
	for category in ["bullets", "shots", "balls"]:
		var list: Array = state.get(category, [])
		for item in list:
			var key: String = category + str(item.get("id", 0))
			alive[key] = true
			var n: Node3D
			if not entities.has(key):
				n = make_projectile(str(item.get("color", "cyan")), category, int(item.get("level", 1)))
				entities[key] = n
				add_child(n)
				n.position = point(float(item.get("x", 0.5)), float(item.get("y", 0.5)))
			else:
				n = entities[key]
			var target := point(float(item.get("x", 0.5)), float(item.get("y", 0.5)))
			if category == "balls":
				target.y = 0.9
				# Stored marbles orbit gently within the vessel rather than lying flat.
			n.set_meta("target", target)
	for key in entities.keys():
		if not alive.has(key):
			entities[key].queue_free()
			entities.erase(key)
	for event in state.get("fx", []):
		var id: String = str(event.get("id", ""))
		if not seen_fx.has(id):
			seen_fx[id] = true
			spawn_effect(event)
	if seen_fx.size() > 512:
		var keys: Array = seen_fx.keys()
		for i in range(256):
			seen_fx.erase(keys[i])

func make_projectile(color_name: String, category: String, level: int) -> Node3D:
	var n := Node3D.new()
	var color: Color = cyan if color_name == "cyan" else coral
	var r: float = 0.19 + min(level - 1, 4) * 0.065
	if category == "balls":
		r *= 1.2
	var shell := material(color, 0.55, 0.7)
	sphere(n, r, Vector3.ZERO, shell)
	sphere(n, r * 0.46, Vector3(0, 0.04, 0.10), material(color.lightened(0.6), 0.1, 2.5))
	var band := ring(n, r * 1.12, 0.026, Vector3.ZERO, pale)
	band.rotation.x = PI / 2
	if category != "balls":
		var direction: float = 1.0 if category == "shots" else -1.0
		for i in range(3):
			var tail := sphere(n, r * (0.68 - i * 0.16), Vector3(0, 0, direction * (0.25 + i * 0.19)), material(color, 0.0, 1.0))
			tail.scale = Vector3(0.65, 0.55, 1.7)
	return n

func spawn_effect(event: Dictionary) -> void:
	var type: String = str(event.get("type", "hit"))
	var color: Color = cyan if str(event.get("color", "cyan")) == "cyan" else coral
	var origin := point(float(event.get("x", 0.5)), float(event.get("y", 0.5)))
	if type == "hit":
		origin = boss.position
		boss_recoil = 1.0
	var parent := Node3D.new()
	add_child(parent)
	parent.position = origin
	var hoop := ring(parent, 0.45, 0.035, Vector3.ZERO, material(color, 0, 2))
	if type == "capture" or type == "merge":
		for i in range(10):
			var a: float = i * TAU / 10
			var part := sphere(parent, 0.065, Vector3(cos(a), 0.15, sin(a)) * 0.8, material(color, 0, 1.5))
			part.set_meta("direction", Vector3(cos(a), 0.3, sin(a)))
	else:
		hoop.rotation.x = PI / 2
		for i in range(13):
			var direction := Vector3(sin(i * 2.4), cos(i * 1.7) * 0.7, cos(i * 2.4)).normalized()
			var part := box(parent, Vector3(0.055, 0.055, 0.25), Vector3.ZERO, material(color, 0.2, 2))
			part.set_meta("direction", direction)
			part.look_at_from_position(Vector3.ZERO, direction)
	effects.append({"node": parent, "age": 0.0, "kind": type, "ring": hoop})

func _process(delta: float) -> void:
	clock_time += delta
	if boss == null:
		return
	var boss_data: Dictionary = state.get("boss", {})
	var boss_x: float = (float(boss_data.get("x", 0.5)) - 0.5) * 14.0
	boss.position.x = lerpf(boss.position.x, boss_x, 1.0 - exp(-delta * 8.0))
	boss.position.y = 2.0 + sin(clock_time * 1.7) * 0.14
	boss_recoil = maxf(0.0, boss_recoil - delta * 4)
	boss.position.z = -6.8 - boss_recoil * 0.22
	core.scale = Vector3.ONE * (1.0 + sin(clock_time * 3.5) * 0.045 + boss_recoil * 0.18)
	for i in range(gimbals.size()):
		gimbals[i].rotate_y(delta * (0.18 + i * 0.07) * (-1.0 if i == 1 else 1.0))
	var receiver_data: Dictionary = state.get("receiver", {})
	var receiver_x: float = (float(receiver_data.get("x", 0.5)) - 0.5) * 14
	receiver.position.x = lerpf(receiver.position.x, receiver_x, 1.0 - exp(-delta * 15))
	receiver.rotation.z = lerpf(receiver.rotation.z, clampf((receiver_x - receiver.position.x) * -0.035, -0.10, 0.10), delta * 8)
	for key in entities:
		var n: Node3D = entities[key]
		var target: Vector3 = n.get_meta("target", n.position)
		n.position = n.position.lerp(target, 1.0 - exp(-delta * 23))
		n.rotation.y += delta * 1.5
	for index in range(effects.size() - 1, -1, -1):
		var e: Dictionary = effects[index]
		e["age"] = float(e["age"]) + delta
		var age: float = e["age"]
		var parent: Node3D = e["node"]
		var capture: bool = e["kind"] == "capture" or e["kind"] == "merge"
		var duration: float = 0.65 if capture else 0.48
		if age >= duration:
			parent.queue_free()
			effects.remove_at(index)
			continue
		var hoop: Node3D = e["ring"]
		var progress: float = age / duration
		var radius: float = (1.0 - progress) * 1.9 if capture else 0.4 + progress * 4.0
		hoop.scale = Vector3(radius, maxf(0.05, 1 - progress), radius)
		for child in parent.get_children():
			if not child.has_meta("direction"):
				continue
			var direction: Vector3 = child.get_meta("direction")
			if capture:
				child.position = direction * pow(1.0 - progress, 2) * 1.2
				child.position.y += sin(progress * PI) * 0.45
			else:
				child.position = direction * (age * 5.0 - age * age * 3.0)
				child.position.y -= age * age * 2
			child.scale = Vector3.ONE * maxf(0.01, (1.0 - progress) * (1.0 - progress))
