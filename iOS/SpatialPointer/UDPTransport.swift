import Foundation
import Network

/// All access and callbacks use the main queue. UDP ready means local availability,
/// not an acknowledgement from Blender. Keep at most four pending datagrams.
final class UDPTransport {
    enum Status { case ready, waiting(String), failed(String) }
    var onStatus: ((Status) -> Void)?
    private(set) var ready = false
    private(set) var sentCount = 0
    private(set) var skippedCount = 0
    private var connection: NWConnection?
    private var inFlight = 0
    var canSend: Bool { ready && inFlight < 4 }

    func start(_ settings: ConnectionSettings) {
        let parameters = NWParameters.udp
        parameters.requiredInterfaceType = .wifi
        let connection = NWConnection(host: NWEndpoint.Host(settings.host),
                                      port: NWEndpoint.Port(rawValue: settings.port)!,
                                      using: parameters)
        self.connection = connection
        connection.stateUpdateHandler = { [weak self, weak connection] state in
            guard let self, let connection, self.connection === connection else { return }
            switch state {
            case .ready:
                self.ready = true
                self.onStatus?(.ready)
            case .waiting(let error):
                self.ready = false
                self.onStatus?(.waiting(error.localizedDescription))
            case .failed(let error):
                self.ready = false
                self.onStatus?(.failed(error.localizedDescription))
            default: break
            }
        }
        connection.start(queue: .main)
    }

    func send(_ data: Data) {
        guard canSend, let connection else { skippedCount += 1; return }
        inFlight += 1
        connection.send(content: data, contentContext: .defaultMessage, isComplete: true,
                        completion: .contentProcessed { [weak self, weak connection] error in
            guard let self, let connection, self.connection === connection else { return }
            self.inFlight -= 1
            if let error {
                self.ready = false
                self.onStatus?(.failed(error.localizedDescription))
            } else {
                self.sentCount += 1
            }
        })
    }

    func stop(finalPacket: Data?) {
        guard let connection else { return }
        self.connection = nil
        ready = false
        onStatus = nil
        connection.stateUpdateHandler = nil
        if let finalPacket {
            // Best effort: iOS suspension / packet loss can defeat this; Blender also
            // releases after its independent 0.75-second signal timeout.
            connection.send(content: finalPacket, contentContext: .defaultMessage,
                            isComplete: true, completion: .contentProcessed { _ in connection.cancel() })
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { connection.cancel() }
        } else {
            connection.cancel()
        }
    }

    deinit { connection?.cancel() }
}
