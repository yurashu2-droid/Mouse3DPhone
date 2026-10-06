import Foundation

public enum InputError: LocalizedError {
    case host, port, token, pose

    public var errorDescription: String? {
        switch self {
        case .host: return "PCのIPv4アドレスを入力してください（例：192.168.1.12）。"
        case .port: return "ポートは1〜65535の整数を入力してください。"
        case .token: return "BlenderのLAN用トークンを入力してください（8文字以上）。"
        case .pose: return "位置・回転の計測値が無効です。"
        }
    }
}

public struct ConnectionSettings {
    public let host: String
    public let port: UInt16
    public let token: String

    public init(host: String, port: String, token: String) throws {
        let host = host.trimmingCharacters(in: .whitespacesAndNewlines)
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { throw InputError.host }
        var octets: [UInt8] = []
        for part in parts {
            guard !part.isEmpty, part.allSatisfy({ $0.isASCII && $0.isNumber }),
                  let number = UInt8(part), String(number) == String(part) else { throw InputError.host }
            octets.append(number)
        }
        guard octets[0] > 0, octets[0] != 127, octets[0] < 224,
              octets[3] != 255 else { throw InputError.host }
        let portText = port.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !portText.isEmpty, portText.allSatisfy({ $0.isASCII && $0.isNumber }),
              let port = UInt16(portText), port > 0 else { throw InputError.port }
        let token = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard token.utf8.count >= 8, token.utf8.count <= 256 else { throw InputError.token }
        self.host = host
        self.port = port
        self.token = token
    }
}

public struct PhonePose: Equatable {
    public let position: [Double]
    /// Explicit wire order: w, x, y, z. Never serialize SIMD storage.
    public let rotation: [Double]
    public static let identity = try! PhonePose(position: [0, 0, 0], rotation: [1, 0, 0, 0])

    public init(position: [Double], rotation: [Double]) throws {
        guard position.count == 3, rotation.count == 4,
              position.allSatisfy({ $0.isFinite && abs($0) <= 100000 }),
              rotation.allSatisfy({ $0.isFinite && abs($0) <= 1000000 }) else { throw InputError.pose }
        let length = sqrt(rotation.reduce(0) { $0 + $1 * $1 })
        guard length.isFinite, length >= 1e-12 else { throw InputError.pose }
        self.position = position
        self.rotation = rotation.map { $0 / length }
    }
}

public struct PosePacket: Encodable {
    public let v: Int = 1
    public let session: String
    public let seq: Int64
    public let position: [Double]
    public let rotation: [Double]
    public let space: String = "ARKIT"
    public let clutch: Bool
    public let grab: Bool
    public let tracking: Bool
    public let token: String

    public func encoded() throws -> Data { try JSONEncoder().encode(self) }
}
