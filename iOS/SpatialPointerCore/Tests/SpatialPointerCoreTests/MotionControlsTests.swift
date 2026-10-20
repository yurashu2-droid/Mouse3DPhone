import XCTest
@testable import SpatialPointerCore

final class MotionControlsTests: XCTestCase {
    private func sample(_ x: Double, angle: Double = 0) -> PhonePose {
        try! PhonePose(position: [x, 0, 0], rotation: [cos(angle / 2), 0, 0, sin(angle / 2)])
    }

    func testTranslationAndRotationHaveIndependentGains() {
        var controls = MotionControls()
        controls.setSensitivity(translation: 2, rotation: 0.5)
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        controls.update(pose: sample(1, angle: .pi / 2), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 2, accuracy: 1e-10)
        XCTAssertEqual(controls.pose.rotation[0], cos(.pi / 8), accuracy: 1e-10)
        XCTAssertEqual(controls.pose.rotation[3], sin(.pi / 8), accuracy: 1e-10)
    }

    func testChangingGainsOnlyAffectsFutureDeltas() {
        var controls = MotionControls()
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        controls.update(pose: sample(1, angle: .pi / 4), tracked: true)
        let before = controls.pose
        controls.setSensitivity(translation: 3, rotation: 2)
        XCTAssertEqual(controls.pose, before)
        controls.update(pose: sample(1, angle: .pi / 4), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 1, accuracy: 1e-10)
        controls.update(pose: sample(2, angle: .pi / 2), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 4, accuracy: 1e-10)
        XCTAssertEqual(controls.pose.rotation[0], cos(3 * .pi / 8), accuracy: 1e-10)
    }

    func testReleaseFreezesAndRepressDoesNotCatchUpRepositioning() {
        var controls = MotionControls()
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        controls.update(pose: sample(1), tracked: true)
        controls.setMoveHeld(false)
        controls.update(pose: sample(20, angle: .pi / 2), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 1, accuracy: 1e-10)
        controls.setMoveHeld(true)
        controls.update(pose: sample(21, angle: .pi / 2), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 2, accuracy: 1e-10)
        XCTAssertEqual(controls.pose.rotation, [1, 0, 0, 0])
    }

    func testGrabTakesPriorityAndReleaseKeepsMovementHeld() {
        var controls = MotionControls()
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        XCTAssertTrue(controls.following)
        XCTAssertFalse(controls.grabbing)
        controls.setGrabHeld(true)
        XCTAssertTrue(controls.grabbing)
        controls.update(pose: sample(1), tracked: true)
        controls.setGrabHeld(false)
        XCTAssertTrue(controls.following)
        XCTAssertFalse(controls.grabbing)
        controls.update(pose: sample(2), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 2, accuracy: 1e-10)
        controls.setMoveHeld(false)
        XCTAssertFalse(controls.following)
        controls.setGrabHeld(true)
        XCTAssertTrue(controls.following)
        XCTAssertTrue(controls.grabbing)
        controls.setGrabHeld(false)
        XCTAssertFalse(controls.following)
    }

    func testTrackingRecoveryRequiresFreshPressAndDoesNotJump() {
        var controls = MotionControls()
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        controls.setGrabHeld(true)
        controls.update(pose: sample(1), tracked: true)
        controls.update(pose: sample(10), tracked: false)
        controls.setGrabHeld(true) // A touch while unavailable cannot arm recovery.
        controls.update(pose: sample(20), tracked: true)
        XCTAssertFalse(controls.moveHeld)
        XCTAssertFalse(controls.grabHeld)
        XCTAssertFalse(controls.following)
        XCTAssertFalse(controls.grabbing)
        XCTAssertEqual(controls.pose.position[0], 1, accuracy: 1e-10)
        controls.setMoveHeld(true)
        controls.update(pose: sample(21), tracked: true)
        XCTAssertEqual(controls.pose.position[0], 2, accuracy: 1e-10)
        XCTAssertFalse(controls.grabbing)
    }

    func testQuaternionSignAndSmallAngleRemainContinuous() {
        var controls = MotionControls()
        controls.setSensitivity(translation: 1, rotation: 5)
        controls.update(pose: sample(0), tracked: true)
        controls.setMoveHeld(true)
        controls.update(pose: try! PhonePose(position: [0, 0, 0], rotation: [-1, 0, 0, 0]), tracked: true)
        XCTAssertEqual(controls.pose.rotation, [1, 0, 0, 0])
        controls.update(pose: sample(0, angle: 1e-8), tracked: true)
        XCTAssertEqual(controls.pose.rotation[3], 2.5e-8, accuracy: 1e-12)
    }

    func testSensitivityRangeAndResetRetainPreferences() {
        var controls = MotionControls()
        controls.setSensitivity(translation: -1, rotation: 10)
        XCTAssertEqual(controls.translationSensitivity, 0.1)
        XCTAssertEqual(controls.rotationSensitivity, 5)
        controls.setSensitivity(translation: .nan, rotation: .infinity)
        XCTAssertEqual(controls.translationSensitivity, 1)
        XCTAssertEqual(controls.rotationSensitivity, 1)
        controls.setSensitivity(translation: 2, rotation: 3)
        controls.update(pose: sample(0), tracked: true)
        controls.setGrabHeld(true)
        controls.reset()
        XCTAssertEqual(controls.translationSensitivity, 2)
        XCTAssertEqual(controls.rotationSensitivity, 3)
        XCTAssertEqual(controls.pose, .identity)
        XCTAssertFalse(controls.following)
    }
}
