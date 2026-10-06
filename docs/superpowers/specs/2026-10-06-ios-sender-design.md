# Spatial Pointer iOS sender

## Intent
Build a native iPhone controller for the supplied Spatial Pointer Blender 0.1.1 receiver. Real ARKit world tracking supplies XYZ position and orientation; neither tilt nor synthetic motion substitutes for translation. Deliver an Xcode project and an unsigned arm64 IPA built on macOS, with GitHub Actions as the Windows user's build route.

## Scope and architecture
- iOS 16.0+, Swift 5, SwiftUI, ARKit, SceneKit camera preview, Network.framework UDP; no external application dependencies.
- Separate Foundation-only Swift package owns typed packets, settings validation and follow/grab/session state. Compile those same source files into the iOS target; package tests run on macOS.
- Send UDP JSON v1 at selectable 30 or 60 Hz, `space=ARKIT`, quaternion explicitly `[w,x,y,z]`. Use exactly the existing receiver protocol and token. Source address/port stay stable for the connection.
- User supplies PC IPv4, port 5005 by default, and the Blender LAN pairing token. Only host/port persist; token remains in memory. No discovery, cloud service or incoming commands.
- Portrait Japanese UI: settings, camera preview, real tracking state, local send count, independent Follow toggle, large hold-to-grab control. Accessibility action permits a deliberate grab/release toggle. A send success never claims Blender acknowledged receipt.
- Follow starts paused. Clutch freezes movement while keeping an existing grab; tracking loss, stale frames (0.25 s), background, errors or stop release it. Recovery never resumes a held grab without a fresh press. Three tracked release packets arm local grab controls.
- Reset AR tracking changes session ID and resets sequence; wait 0.85 s before sending the new session, allowing the receiver's 0.75 s sender gate to expire. New connections also wait 0.85 s. Initializing/limited/unavailable tracking sends `tracking=false`.
- UIKit touch down/up/cancel implements hold behavior. Scene inactivity and settings presentation stop input. Keep the screen awake only while sending.
- Camera and local-network permission descriptions; privacy manifest declares only app-owned UserDefaults access, no collection or tracking.

## Delivery and validation
Keep the original Blender code under `blender/` with its license, protocol and install ZIP. Add macOS build/package scripts, Swift unit tests, a Swift-generated fixture validated with the real Python receiver, and a narrowly scoped manual iPhone checklist. CI runs these checks before uploading the unsigned IPA and SHA-256 digest.

The current host is Windows without Swift or Xcode. Local checks must be reported separately from macOS compilation and actual iPhone/Blender verification. An unsigned IPA cannot normally be installed on a stock iPhone until signed by the user's installation tool.

## Rulings
Design approval is not requested, per the user's AGENTS instructions. Implement inline and review once at the feature boundary; do not introduce new Blender features or change its UDP interface.
