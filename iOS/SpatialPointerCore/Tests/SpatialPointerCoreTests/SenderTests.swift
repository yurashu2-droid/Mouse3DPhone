import Foundation
import XCTest
@testable import SpatialPointerCore

final class SenderTests: XCTestCase {
    let pose = try! PhonePose(position: [0.1, 0.2, -0.3], rotation: [0.5, 0.5, 0.5, 0.5])

    func armedState() -> SenderState {
        var state = SenderState()
        state.update(pose: pose, tracked: true)
        for _ in 0..<3 { _ = state.nextPacket(token: "test-token") }
        return state
    }

    func testWireUsesNumbersBooleansAndWXYZ() throws {
        var state = armedState()
        state.setFollow(true)
        state.setGrab(true)
        let packet = state.nextPacket(token: "test-token")
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: packet.encoded()) as? [String: Any])
        XCTAssertEqual(object["v"] as? Int, 1)
        XCTAssertEqual(object["space"] as? String, "ARKIT")
        XCTAssertEqual(object["position"] as? [Double], pose.position)
        XCTAssertEqual(object["rotation"] as? [Double], pose.rotation)
        XCTAssertEqual(object["clutch"] as? Bool, true)
        XCTAssertEqual(object["grab"] as? Bool, true)
        XCTAssertEqual(object["tracking"] as? Bool, true)
        XCTAssertEqual(object["token"] as? String, "test-token")
    }

    func testClutchKeepsHeldObjectAndResumes() {
        var state = armedState()
        state.setFollow(true)
        state.setGrab(true)
        state.setFollow(false)
        let paused = state.nextPacket(token: "test-token")
        XCTAssertFalse(paused.clutch)
        XCTAssertTrue(paused.grab)
        state.setFollow(true)
        XCTAssertTrue(state.nextPacket(token: "test-token").grab)
    }

    func testTrackingLossReleasesAndRecoveryRequiresNewPress() {
        var state = armedState()
        state.setGrab(true)
        state.update(pose: pose, tracked: false)
        XCTAssertFalse(state.nextPacket(token: "test-token").grab)
        state.update(pose: pose, tracked: true)
        for _ in 0..<3 { XCTAssertFalse(state.nextPacket(token: "test-token").grab) }
        XCTAssertTrue(state.canGrab)
        XCTAssertFalse(state.grabbing)
        state.setGrab(true)
        XCTAssertTrue(state.nextPacket(token: "test-token").grab)
    }

    func testHandshakeDoesNotAllowEarlyGrab() {
        var state = SenderState()
        state.update(pose: pose, tracked: true)
        state.setGrab(true)
        XCTAssertFalse(state.grabbing)
        for _ in 0..<3 { _ = state.nextPacket(token: "test-token") }
        XCTAssertTrue(state.canGrab)
    }

    func testSequenceAndResetSession() {
        var state = armedState()
        let before = state.nextPacket(token: "test-token")
        XCTAssertEqual(state.nextPacket(token: "test-token").seq, before.seq + 1)
        state.reset()
        let reset = state.nextPacket(token: "test-token")
        XCTAssertNotEqual(reset.session, before.session)
        XCTAssertEqual(reset.seq, 0)
        XCTAssertFalse(reset.grab)
        XCTAssertFalse(reset.tracking)
        XCTAssertFalse(reset.clutch)
    }

    func testPoseRejectsNonfiniteAndNormalizesQuaternion() throws {
        XCTAssertThrowsError(try PhonePose(position: [.nan, 0, 0], rotation: [1, 0, 0, 0]))
        XCTAssertThrowsError(try PhonePose(position: [0, 0, 0], rotation: [0, 0, 0, 0]))
        XCTAssertThrowsError(try PhonePose(position: [100001, 0, 0], rotation: [1, 0, 0, 0]))
        XCTAssertEqual(try PhonePose(position: [0, 0, 0], rotation: [2, 0, 0, 0]).rotation, [1, 0, 0, 0])
    }

    func testSettingsRejectInvalidIPv4PortAndMissingToken() throws {
        let settings = try ConnectionSettings(host: " 192.168.1.12 ", port: "5005", token: " test-token ")
        XCTAssertEqual(settings.host, "192.168.1.12")
        XCTAssertEqual(settings.token, "test-token")
        for host in ["", "localhost", "127.0.0.1", "0.0.0.0", "256.1.1.1", "224.0.0.1", "192.168.1", "192.168.01.2"] {
            XCTAssertThrowsError(try ConnectionSettings(host: host, port: "5005", token: "test-token"), host)
        }
        for port in ["0", "65536", "abc"] {
            XCTAssertThrowsError(try ConnectionSettings(host: "192.168.1.2", port: port, token: "test-token"))
        }
        XCTAssertThrowsError(try ConnectionSettings(host: "192.168.1.2", port: "5005", token: ""))
    }
}
