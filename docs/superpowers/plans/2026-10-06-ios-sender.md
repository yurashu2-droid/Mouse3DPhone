# iOS Sender Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user's AGENTS instructions override approval waits and excessive verification.

**Goal:** Deliver the ARKit iPhone controller and a reproducible unsigned IPA in Mouse3DPhone.

**Architecture:** A Foundation-only protocol/state package feeds a main-thread ARKit controller and bounded UDP transport. SwiftUI presents the camera and touch controls. GitHub's macOS runner builds the unsigned app.

**Tech Stack:** iOS 16+, Swift 5, SwiftUI, ARKit, SceneKit, Network, Python, Xcode.

**Spec:** `docs/superpowers/specs/2026-10-06-ios-sender-design.md`

## Global Constraints
- Existing Blender UDP JSON v1, ARKIT basis, wxyz quaternion, port 5005.
- 30/60 Hz; stale frames 0.25 s; new session hold-off 0.85 s; receiver timeout 0.75 s.
- No external iOS dependencies or phone token persistence. No false acknowledgement status.
- Windows cannot compile iOS; use macOS CI. Original Blender logic stays unchanged.

## Review Focus
- Touch cancellation/background must release instead of leaving a grab latched.
- Tracking recovery and connection replacement require a new grab press.
- Session replacement must outwait Blender's sender gate.
- Sender queue is bounded and errors stop motion.
- Unsigned artifact must contain a real arm64 Mach-O app, not source renamed as IPA.

### Task 1: Wire protocol and control state
**Files:** `iOS/SpatialPointerCore/{Package.swift,Sources/*,Tests/*}`, `tools/check_wire.py`, `blender/`.
**Interfaces:** `PhonePose`, `ConnectionSettings`, `SenderState.nextPacket(token:) -> PosePacket`, `PosePacket.encoded() -> Data`.
- [ ] Write Swift tests for wire types/order, finite pose validation, sequence reset, tracking recovery and clutch preserving grab.
- [ ] Implement packet/settings/state package and executable fixture producer.
- [ ] Run `swift test --package-path iOS/SpatialPointerCore` on macOS; parse Swift-generated packets with Blender `parse_packet` and `SessionGate`.

### Task 2: iPhone application
**Files:** `iOS/SpatialPointer/{App.swift,Controller.swift,UDPTransport.swift,ContentView.swift,HoldControl.swift,Info.plist,PrivacyInfo.xcprivacy,Assets.xcassets/*}`.
**Interfaces:** Task 1 models; `UDPTransport.start`, `send`, `stop`; published `PhoneController` UI state.
- [ ] Add ARKit pose sampling, frame watchdog, camera permissions and lifecycle stop.
- [ ] Add IPv4 UDP transport with at most four in-flight sends and best-effort release on stop.
- [ ] Add Japanese settings, camera/status, follow/reset and hold-to-grab UI.
- [ ] Add Xcode project/shared scheme with the exact package source files.

### Task 3: Build and delivery
**Files:** `tools/build_unsigned.sh`, `tools/package_ipa.py`, `.github/workflows/ios-unsigned.yml`, `README.md`, `docs/VERIFICATION_IOS.md`.
**Interfaces:** macOS Xcode builds `SpatialPointer.app`; packager validates arm64 executable and creates `dist/SpatialPointer-unsigned.ipa` plus digest.
- [ ] Test packager with a realistic temporary app and malformed/wrong-architecture cases.
- [ ] Validate local project/plists/scheme and the original Blender suite once.
- [ ] Perform one feature-level review, resolve material findings.
- [ ] Commit and push one meaningful implementation to the supplied empty repository; inspect macOS CI, fix build failures and retrieve artifact if access allows.
- [ ] Document actual results separately from tests requiring iPhone/Blender hardware.
