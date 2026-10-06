import Foundation

/// Main-thread state; intentionally independent of ARKit, UIKit and networking.
public struct SenderState {
    public private(set) var session = UUID().uuidString
    public private(set) var sequence: Int64 = 0
    public private(set) var pose = PhonePose.identity
    public private(set) var tracked = false
    public private(set) var following = false
    public private(set) var grabbing = false
    private var releaseFrames = 0
    public var canGrab: Bool { tracked && releaseFrames >= 3 }

    public init() {}

    public mutating func reset() { self = SenderState() }

    public mutating func update(pose: PhonePose, tracked: Bool) {
        self.pose = pose
        self.tracked = tracked
        if !tracked {
            grabbing = false
            releaseFrames = 0
        }
    }

    public mutating func setFollow(_ value: Bool) { following = value }

    public mutating func setGrab(_ value: Bool) {
        grabbing = value && canGrab
    }

    public mutating func stop() {
        following = false
        update(pose: pose, tracked: false)
    }

    public mutating func nextPacket(token: String) -> PosePacket {
        // At 60 Hz exhaustion would take billions of years; avoid integer traps anyway.
        if sequence == Int64.max { reset() }
        let packet = PosePacket(session: session, seq: sequence,
                                position: pose.position, rotation: pose.rotation,
                                clutch: following, grab: grabbing && tracked,
                                tracking: tracked, token: token)
        sequence += 1
        if tracked && !grabbing { releaseFrames = min(releaseFrames + 1, 3) }
        return packet
    }
}
