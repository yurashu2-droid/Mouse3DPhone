import Combine
import Foundation
import UIKit

/// Refuse redirects so the pairing credential is only sent to the configured PC.
private final class PreviewRedirectPolicy: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

/// Main-thread client. One request in flight; timer bounds all requests to five per second.
final class PointerPreview: ObservableObject {
    @Published private(set) var image: UIImage?
    @Published private(set) var status = "ポインタ視点はOFFです。"
    private var session: URLSession?
    private var task: URLSessionDataTask?
    private var timer: Timer?
    private var endpoint: URL?
    private var token: String?
    private var generation = UUID()
    private var needsStatus = true
    private var lastStatusAt = Date.distantPast

    private struct ServerStatus: Decodable {
        let ready: Bool
        let message: String
        let frames: Int
        let age_seconds: Double?
    }

    func start(settings: ConnectionSettings, port: String) {
        stop()
        guard let previewSettings = try? ConnectionSettings(host: settings.host, port: port, token: settings.token),
              let endpoint = URL(string: "http://\(previewSettings.host):\(previewSettings.port)") else {
            status = "視点ポートは1〜65535の整数を入力してください。"
            return
        }
        self.endpoint = endpoint
        token = previewSettings.token
        needsStatus = true
        lastStatusAt = .distantPast
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        configuration.httpCookieStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.urlCredentialStorage = nil
        configuration.timeoutIntervalForRequest = 3
        configuration.timeoutIntervalForResource = 3
        configuration.httpMaximumConnectionsPerHost = 1
        session = URLSession(configuration: configuration, delegate: PreviewRedirectPolicy(), delegateQueue: .main)
        status = "Blenderのポインタ視点に接続中…"
        let timer = Timer(timeInterval: 0.2, repeats: true) { [weak self] _ in self?.poll() }
        self.timer = timer
        RunLoop.main.add(timer, forMode: .common)
        poll()
    }

    func stop() {
        generation = UUID()
        timer?.invalidate()
        timer = nil
        task?.cancel()
        task = nil
        session?.invalidateAndCancel()
        session = nil
        token = nil
        endpoint = nil
        image = nil
        status = "ポインタ視点は停止中です。"
    }

    private func poll() {
        guard task == nil, let session, let endpoint, let token else { return }
        let requestingStatus = needsStatus || Date().timeIntervalSince(lastStatusAt) >= 1
        if requestingStatus { lastStatusAt = Date() }
        var request = URLRequest(url: endpoint.appendingPathComponent(requestingStatus ? "status" : "frame.png"),
                                 cachePolicy: .reloadIgnoringLocalAndRemoteCacheData, timeoutInterval: 3)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("no-store, no-cache", forHTTPHeaderField: "Cache-Control")
        let operation = generation
        let task = session.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self, self.generation == operation else { return }
                self.task = nil
                self.receive(data: data, response: response, error: error, requestingStatus: requestingStatus)
            }
        }
        self.task = task
        task.resume()
    }

    private func receive(data: Data?, response: URLResponse?, error: Error?, requestingStatus: Bool) {
        guard error == nil, let response = response as? HTTPURLResponse else {
            image = nil
            status = "Blenderに接続できません。Phone pointer view、視点ポート、PCのファイアウォールを確認してください。"
            needsStatus = true
            return
        }
        switch response.statusCode {
        case 401:
            stop()
            status = "視点の認証に失敗しました。Blenderと同じトークンを接続設定に入力してください。"
        case 503:
            image = nil
            status = "映像を準備中です。Blenderで3Dビューを表示してください。"
            needsStatus = true
        case 200:
            if requestingStatus {
                guard let data, let server = try? JSONDecoder().decode(ServerStatus.self, from: data) else {
                    status = "Blenderから視点の状態を取得できません。"
                    return
                }
                let stale = server.age_seconds.map { $0 > 2 } ?? false
                needsStatus = !server.ready || stale
                if !server.ready {
                    image = nil
                    status = server.message.isEmpty ? "Blenderの視点映像はまだ利用できません。" : server.message
                } else if stale {
                    image = nil
                    status = "映像が更新されていません。Blenderの3Dビューを確認してください。"
                } else {
                    status = "ポインタ視点 · 最大5回／秒"
                }
            } else if response.mimeType == "image/png", let data, let frame = UIImage(data: data) {
                image = frame
                status = "ポインタ視点 · 最大5回／秒"
            } else {
                image = nil
                status = "視点映像を読み込めません。Blenderの拡張機能を確認してください。"
                needsStatus = true
            }
        default:
            image = nil
            status = "視点を利用できません。BlenderでPhone pointer viewをONにし、視点ポートを合わせてください。"
            needsStatus = true
        }
    }

    deinit {
        timer?.invalidate()
        task?.cancel()
        session?.invalidateAndCancel()
    }
}
