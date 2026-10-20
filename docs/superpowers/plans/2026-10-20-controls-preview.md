# Phone Controls and Pointer View Implementation Plan

Goal: deliver phone-adjustable independent sensitivities, two hold-to-operate buttons, and optional first-person Blender preview.

Architecture: keep UDP v1 unchanged and apply relative sensitivity in the phone core. Blender captures preview on its main thread and serves PNG snapshots over paired-token HTTP. Two disjoint implementation units run in parallel; the main agent integrates metadata, packages and validates the live GPU path.

Spec: ../specs/2026-10-20-controls-preview.md

Global constraints: iOS 16+, Blender 4.2+, no external dependencies; no token logging; preserve existing diagnostic tools in the original checkout; no unnecessary standalone reviews/builds per small edit.

## Tasks

- [x] iOS unit: edit only iOS/; add relative sensitivity core math and tests, two hold controls, persisted sliders, preview URLSession client/UI and local-network ATS configuration. Keep legacy protocol fixtures usable. No version/project generator edits (integration owns these).
- [x] Blender unit: edit only blender/; add dependency-free preview transport/PNG with focused tests and GPU capture module; wire preview settings/start/stop lifecycle into addon/runtime. Extension manifest version 0.2.0. No live Blender mutations by worker; integration validates GPU.
- [x] Integration: regenerate Xcode project with version 0.3.0 (3); package extension zip deterministically, update CI artifacts and concise setup docs; preserve and integrate original standalone receiver changes deliberately.
- [ ] Verification: related Python suites once per meaningful change set; Swift tests/protocol fixture and iOS build via one CI run; live GPU frame and HTTP authentication checks. Review combined changes once; fix only task-relevant defects.
- [ ] Deliver versioned IPA and addon zip, their verification status, and short install/use instructions.

Review focus: sensitivity changes and clutch transitions must not jump; loss/recovery must not resume a held grab; simultaneous buttons need explicit priority; preview cannot touch bpy off main thread or mutate the viewport; stopping preview or receiver frees network/GPU resources.

Evidence: GPUOffScreen.draw_view3d + UBYTE framebuffer readback succeeded in Blender 5.2.2 LTS, 240x135 RGBA = 129600 bytes with nonconstant pixels. No scene/object changes were made.

Verification evidence: 69 Python tests passed; Blender5.2.2 background smoke passed; actual GUI capture served a 480x270 PNG with authorized HTTP200 and unauthorized401, then released HTTP/GPU resources. Combined review found and corrected the CI pytest invocation. macOS Swift tests/build remain the final gate.
