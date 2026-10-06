# Spatial Pointer Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task, retaining test evidence.

**Goal:** Deliver an installable Blender prototype for a six-degree-of-freedom spatial pointer.
**Architecture:** Pure pose/protocol math separated from a bounded UDP receiver and Blender UI/runtime. A keyboard simulator feeds the same pose mapper as UDP.
**Tech Stack:** Python 3.11+ in Blender 4.2+, stdlib, bpy/mathutils/bmesh/blf.
**Spec:** docs/superpowers/specs/2026-10-06-spatial-pointer-design.md

## Global Constraints
- No generated images, remote repository writes, iPhone/ARKit runtime claims or sculpt promises.
- Self-contained extension, Blender minimum 4.2.0.
- Network off by default, loopback default, explicit authenticated LAN.
- Preserve existing user scenes; bpy only on main thread.

## Review Focus
- Non-finite, oversized, ill-typed or stale packets must not mutate the pointer.
- Clutch/gain/tracking recovery must not teleport the pointer or re-grab unexpectedly.
- Datagrams from a competing sender must not control an active session.
- Undo/file load/unregister must not leave a live socket or invalid object reference.
- Extension ZIP must contain its manifest at root and no development caches.

### Task 1 — pose and transport
Files: spatial_pointer/core.py, spatial_pointer/transport.py, tests/test_core.py, tests/test_transport.py.
Interfaces: Pose(position, rotation), Packet; parse_packet(bytes, token); PoseMapper.update(pose, follow, gain, tracking); SessionGate.accept(packet, peer, now); UDPReceiver.poll().
- [x] Write failing tests for the interfaces and malformed inputs.
- [x] Run pytest, observe missing implementation.
- [x] Implement bounded validation, basis transform, mapping and transport.
- [x] Run the full pytest suite; commit.

### Task 2 — Blender runtime
Files: spatial_pointer/__init__.py, addon.py, visuals.py; tests/blender_smoke.py.
Interfaces: register/unregister; SP runtime create_pointer, start_keyboard/start_udp, stop, grab, release, restore.
- [x] Write executable Blender smoke assertions for registration, helpers, pose application and grabbing.
- [x] Implement panel, helpers, keyboard simulation, main-thread timer and lifecycle handlers.
- [x] Compile all modules and run pure suite. Execute Blender smoke only if binary exists; otherwise explicitly record it as unrun.
- [x] Review cleanup paths and state invariants; commit.

### Task 3 — sender, docs and packages
Files: tools/udp_sender.py, tests/test_sender.py, blender_manifest.toml, README_JA.md, docs/PROTOCOL.md, tools/build_release.py.
- [x] Write sender and package contract tests; run red.
- [x] Implement deterministic demo sender, metadata and Japanese install/use instructions.
- [x] Run full tests, CLI loopback exercise, compile, build and inspect archives.
- [x] Record exact verification limits and deliver extension ZIP plus development kit.
