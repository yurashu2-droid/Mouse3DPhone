# Spatial Pointer v0.1 — design

## Intent and approved scope
Build the Blender-first prototype discussed in this conversation: a pointer with a real 3D position and orientation, not a 2D trackpad and not a view-navigation substitute. Deliver an installable ZIP. This iteration validates the Blender input path using the PC; it does not include a working iPhone app or sculpt deformation.

## Implementation choices
- Self-contained Blender extension, minimum 4.2.0, Python standard library + Blender's bundled bpy/mathutils/bmesh/blf only.
- Native N-panel named Spatial. A visible, non-rendering sphere and direction axes represent the pointer. A floor marker and stem make depth easier to judge.
- An in-Blender keyboard simulator makes first use possible with no external Python installation. A separate UDP sender tests the network path.
- Keyboard: A/D = -/+X, W/S = +/-Y, Q/E = -/+Z. I/K tilt around X, J/L turn around Z, U/O roll around Y. Shift precision. Hold Space grabs the active selected object; release drops. C toggles follow. R rebases without teleporting. F places pointer at selection. Enter finishes. Escape cancels the current grab and stops.
- A new demo scene is created only on explicit button press; existing scenes are not deleted. Helper objects are tagged and non-rendering. The add-on never starts networking automatically on install or file load.
- Grab preserves the full pointer-to-object offset. Each completed grab has an explicit Restore Last Grab action. Sculpt and surface picking are out of scope.
- Relative pose mapper, gain, quaternion rotation, frame-rate-independent positional smoothing, clutch re-anchoring with no jump. Tracking loss freezes; recovery re-anchors.
- UDP JSON v1: position[3], rotation[4] in wxyz order, space BLENDER or ARKIT, clutch bool (true follows), grab bool, tracking bool, session string, seq integer. Localhost bind by default. LAN is explicit and requires a generated pairing token. No remote code or shell execution.
- Socket is non-blocking, input size/rate per tick is bounded, data is finite and typed, sequence/sender checks reject stale/interleaved data. Main-thread bpy timer; no background threads in Blender.
- Timeout 0.75 s freezes motion and releases the grab. A new sender or tracking recovery must release its grab button before a fresh grab can begin.
- Stop, file load, undo/redo, deletion and unregister clean up timers/sockets. No claim of measured phone tracking accuracy or latency.

## Verification
Pure Python tests for validation, quaternion/basis math, clutch/gain/smoothing, sequence/timeouts, loopback sockets and sender data. Static compilation/package checks. A Blender-native smoke test is included; actual Blender launch verification is conditional on a usable binary being available and must not be claimed otherwise.
