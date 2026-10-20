# Phone controls and pointer view

User intent: operate the existing Spatial Pointer independently of selecting an object, avoid repeatedly toggling follow, adjust translation and rotation sensitivity independently on the phone, and see the scene from the pointer's position on the phone.

## Interaction

- Replace the follow toggle with two momentary buttons: pointer movement only, and grab plus movement. Releasing both freezes movement and releases an object. Holding both gives grab priority; releasing grab while movement remains held continues movement without the object.
- No extra follow toggle is required. Sending continues while neither button is held so tracking/recovery and receiver timeouts keep working.
- Tracking loss, reset, network stop and background release held controls. Recovery requires a fresh press, never an automatic grab.
- Persist separate translation and rotation multipliers on the phone, default 1, range 0.1–5. Apply tracked pose deltas so changing sensitivity or holding/releasing movement does not jump the pointer. Preserve v1 packet fields and Blender compatibility; Blender Motion gain remains an additional translation multiplier.

## Pointer view

- Optional phone preview, default off. Blender provides an opt-in "Phone pointer view" setting and HTTP port 5006 (phone setting matches).
- From pointer position, camera looks along pointer +Y with +Z up at identity. Therefore camera world matrix is pointer pose matrix multiplied by +90 degrees about local X, before inversion for GPU view matrix.
- Use GPUOffScreen and the existing visible VIEW_3D context, at 480x270, maximum 5 fps. GPU and bpy access stay on Blender's main thread; a separate HTTP thread serves only immutable frame/status snapshots.
- Encode RGBA to PNG in memory with standard-library zlib/struct. Do not render/save files or change the user's camera/render settings. Keep PC viewport unchanged.
- HTTP GET /frame.png returns image/png (200), not-yet-ready (503), or unauthorized (401). GET /status returns JSON with ready/message/frames/age_seconds. Both require Authorization: Bearer <the same Pairing Token>; no token in URLs or logs. Bind to all IPv4 only with existing LAN/online-access opt-ins; otherwise do not start LAN preview.
- Phone polls at most 5 fps with one request in flight, ephemeral/no-cache URLSession. Explain absent Blender preview, wrong token, and unavailable frame. Stop on background/stop/preview off. ARKit keeps running when displaying the remote view.
- Blender stops stream, removes draw callback, closes HTTP server, frees GPU resources on stop/unregister/scene change. No remote commands, object selection or camera controls exposed.
- Camera inside geometry can be occluded; this is a first-person preview, not a collision-aware camera.

## Delivery and verification

- App 0.3.0 build 3, Blender extension 0.2.0; deliver both installable packages and explain addon upgrade.
- Targeted Swift tests for motion math, sensitivity independence/change continuity, hold priority/release and tracking recovery; Python tests for PNG/authentication/server lifecycle. Existing compatibility fixtures and suites remain passing.
- Prove GPU readback and streamed image in the user's Blender without moving objects, then macOS CI builds actual iPhone arm64 unsigned IPA. Clearly distinguish build/server checks from phone device verification.
- User's AGENTS instructions authorize implementation without separate design/plan approval and require proportionate testing/review.
