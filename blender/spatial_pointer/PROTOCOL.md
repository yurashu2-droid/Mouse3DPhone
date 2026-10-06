# Spatial Pointer UDP protocol v1

This is a LAN/local experimental input protocol, not an encrypted remote-control service.
The Blender receiver never evaluates code, triggers arbitrary operators or runs shell commands.
Every accepted packet can only affect the pointer pose and the constrained grab/follow controls below.

## Transport

- IPv4 UDP. Default port 5005. Default bind address 127.0.0.1.
- LAN is opt-in and binds 0.0.0.0. It requires the pairing token shown in the panel.
- One UTF-8 JSON object per datagram. Maximum 4096 bytes.
- Send 30–60 poses per second as a starting point. This is a suggested send rate, not a measured end-to-end latency guarantee.
- The Blender timer requests 60 updates/s and reads at most 64 datagrams per tick. UI/workload can reduce the real rate.
- No acknowledgement/discovery protocol. A successful send() does not mean Blender received the packet.
- Timeout: 0.75 seconds without an accepted packet freezes the pointer and releases a held object at its last transform.
- No port forwarding, public Wi-Fi, or Internet-facing use. Pairing tokens are transmitted in plain text and provide no confidentiality.

## Packet

```json
{
  "v": 1,
  "session": "phone-session-9d3a",
  "seq": 1,
  "position": [0.10, 0.20, -0.30],
  "rotation": [1.0, 0.0, 0.0, 0.0],
  "space": "ARKIT",
  "clutch": true,
  "grab": false,
  "tracking": true,
  "token": "copy-the-lan-pairing-token"
}
```

| Field | Contract |
|---|---|
| v | Required integer 1; booleans are not accepted as integers |
| session | Required 1–64 ASCII letters/digits or `-_.`; create a new session per sender launch / tracking-world reset |
| seq | Required monotonically increasing integer from 0 to 2^63−1 |
| position | Required array of 3 finite numbers, absolute value ≤100000 |
| rotation | Optional quaternion **[w, x, y, z]**; identity by default; finite, nonzero, normalized on receive |
| space | `BLENDER` (default) or `ARKIT` |
| clutch | Boolean; **true means follow**, false means freeze and release the input anchor. Does NOT automatically release the object |
| grab | Boolean; true means hold the selected object, false means release. Default false |
| tracking | Boolean; false freezes and releases. Default true |
| token | Required exact string match in LAN mode; ignored in loopback mode |

Unknown fields are ignored for forward compatibility. Strings like `"true"`, integer booleans, NaN, Infinity and malformed UTF-8 are rejected. Datagrams from other IP/port/session combinations are ignored while the current session is live. Older/duplicate sequence numbers are ignored.

## Coordinate conventions

The Blender basis is right-handed: +X right, +Y forward, +Z up.
For ARKit-style right-handed +Y-up, -Z-forward poses, the basis change is:

```text
p_blender = (p_arkit.x, -p_arkit.z, p_arkit.y)
q_blender = C * q_arkit * inverse(C)
C = quaternion for +90 degrees around X
```

This is a basis conversion, not screen-relative calibration. The current v0.1 does not infer which direction a physical monitor faces. Camera/world origin changes on the sender must trigger a new `session` and preferably a `tracking=false` interval.

## Relative mapping, clutch and gain

The first valid packet establishes an input reference and does not teleport the pointer.
While following, the receiver computes:

```text
p_target = p_output_anchor + gain * (p_input - p_input_anchor)
q_target = (q_input * inverse(q_input_anchor)) * q_output_anchor
```

It optionally smooths this target. Follow OFF, tracking loss, recenter, gain changes, sender/session changes and reconnection invalidate the input reference. The next usable sample is an anchor; the pointer remains where it was.

The local Follow checkbox and remote clutch must both be true. Sending `clutch=false` every frame during a phone reposition is fine. The phone can still change its position/orientation while the pointer is frozen. Re-enable with the latest current pose, not the old pre-clutch pose.

## Safe grabbing

A new/recovered session must send a tracked `grab=false` frame before a `grab=true` frame can start a grab. A held-down button cannot silently re-grab on reconnection. Do not emit only `grab=true` packets from startup.

Grabbing targets Blender's **active selected object**, not the nearest surface. The full pointer-to-object matrix offset is preserved. Releasing commits its current transform into the add-on's small restoration history; cancellation is an explicit local operation. The sender cannot name arbitrary objects or execute arbitrary Blender commands.

A `tracking=false` packet and a network timeout release immediately. A normal `clutch=false` packet freezes the pointer but keeps the currently held object attached, allowing the controller to be repositioned.

## Scope of the phone integration

The supplied Python sender creates synthetic poses; it does not track a phone.
A future iPhone sender needs real 6DoF world tracking, a UI with separate Follow/Grab controls, tracking-state reporting and this UDP encoder. A browser gyroscope alone is not a replacement for XYZ position tracking.
Do not serialize SIMD quaternion memory directly: explicitly arrange values in the documented wxyz order.
