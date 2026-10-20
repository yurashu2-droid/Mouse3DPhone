import Foundation

/// Relative phone motion and momentary controls, independent of ARKit and networking.
/// SenderState keeps its original wire/fixture semantics; the app supplies this mapped pose.
public struct MotionControls {
    public private(set) var pose = PhonePose.identity
    public private(set) var tracked = false
    public private(set) var moveHeld = false
    public private(set) var grabHeld = false
    public private(set) var translationSensitivity = 1.0
    public private(set) var rotationSensitivity = 1.0
    private var previous: PhonePose?

    public var following: Bool { tracked && (moveHeld || grabHeld) }
    public var grabbing: Bool { tracked && grabHeld }

    public init() {}

    public mutating func setSensitivity(translation: Double, rotation: Double) {
        translationSensitivity = Self.gain(translation)
        rotationSensitivity = Self.gain(rotation)
    }

    private static func gain(_ value: Double) -> Double {
        value.isFinite ? min(5, max(0.1, value)) : 1
    }

    public mutating func setMoveHeld(_ value: Bool) { moveHeld = value && tracked }
    public mutating func setGrabHeld(_ value: Bool) { grabHeld = value && tracked }

    public mutating func reset() {
        pose = .identity
        release()
    }

    /// Invalidates the input baseline so relocalization never moves the pointer.
    public mutating func release() {
        tracked = false
        moveHeld = false
        grabHeld = false
        previous = nil
    }

    public mutating func update(pose input: PhonePose, tracked: Bool) {
        guard tracked else { release(); return }
        self.tracked = true
        defer { previous = input }
        guard following, let previous else { return }
        let position = zip(zip(pose.position, input.position), previous.position).map {
            $0.0.0 + ($0.0.1 - $0.1) * translationSensitivity
        }
        let inversePrevious = [previous.rotation[0], -previous.rotation[1],
                               -previous.rotation[2], -previous.rotation[3]]
        // World-space incremental rotation; pre-multiply to preserve the tracked axes.
        let delta = Self.multiply(input.rotation, inversePrevious)
        let rotation = Self.multiply(Self.power(delta, rotationSensitivity), pose.rotation)
        if let mapped = try? PhonePose(position: position, rotation: rotation) { pose = mapped }
    }

    private static func multiply(_ a: [Double], _ b: [Double]) -> [Double] {
        [a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3],
         a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2],
         a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1],
         a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0]]
    }

    private static func power(_ quaternion: [Double], _ gain: Double) -> [Double] {
        // q and -q are the same orientation. Always take the shortest delta.
        let q = quaternion[0] < 0 ? quaternion.map { -$0 } : quaternion
        let length = sqrt(q[1]*q[1] + q[2]*q[2] + q[3]*q[3])
        guard length > 1e-15 else { return [1, 0, 0, 0] }
        let halfAngle = atan2(length, q[0]) * gain
        let scale = sin(halfAngle) / length
        return [cos(halfAngle), q[1]*scale, q[2]*scale, q[3]*scale]
    }
}
