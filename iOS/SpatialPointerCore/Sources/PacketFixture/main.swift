import Foundation
import SpatialPointerCore

var state = SenderState()
let pose = try PhonePose(position: [0.1, 0.2, -0.3], rotation: [sqrt(0.5), 0, sqrt(0.5), 0])
let token = "fixture-token"
var packets: [PosePacket] = [state.nextPacket(token: token)]
state.update(pose: pose, tracked: true)
for _ in 0..<3 { packets.append(state.nextPacket(token: token)) }
state.setFollow(true)
state.setGrab(true)
packets.append(state.nextPacket(token: token))
state.setFollow(false)
packets.append(state.nextPacket(token: token))
state.update(pose: pose, tracked: false)
packets.append(state.nextPacket(token: token))
state.update(pose: pose, tracked: true)
for _ in 0..<3 { packets.append(state.nextPacket(token: token)) }
state.setGrab(true)
packets.append(state.nextPacket(token: token))
state.stop()
packets.append(state.nextPacket(token: token))
state.reset()
packets.append(state.nextPacket(token: token))
let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
FileHandle.standardOutput.write(try encoder.encode(packets))
FileHandle.standardOutput.write(Data("\n".utf8))
