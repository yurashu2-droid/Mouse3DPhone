import CoreMotion
import SwiftUI
import WebKit

/// A separate tilt-only mode: no AR session or Blender transport is started here.
struct GameView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("bulletPetHost") private var host = ""
    @AppStorage("bulletPetPort") private var port = "8767"
    @State private var code = ""
    @State private var connection: URL?
    @State private var validation = ""

    var body: some View {
        NavigationStack {
            Group {
                if let url = connection {
                    GameWebView(url: url).id(url)
                } else {
                    Form {
                        Section("PCのゲーム画面に表示された接続先") {
                            TextField("PCのIPv4（例：192.168.1.12）", text: $host)
                                .keyboardType(.decimalPad)
                            TextField("HTTPポート", text: $port).keyboardType(.numberPad)
                            TextField("6桁の接続コード", text: $code).keyboardType(.numberPad)
                            Button("ゲームを開く", action: connect)
                            if !validation.isEmpty { Text(validation).foregroundStyle(.red) }
                        }
                        Section {
                            Text("PCで「弾を飼う」を起動し、同じWi-FiまたはUSBテザリングで接続してください。標準ポートは8767です。")
                            Text("カメラは使いません。画面内の参加ボタンを押した後、スマホを縦向きで傾けて操作します。復帰時は参加ボタンで再開してください。")
                        }
                    }
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
            }
            .navigationTitle("弾を飼う")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(connection == nil ? "閉じる" : "接続先へ戻る") {
                        if connection == nil { dismiss() } else { connection = nil }
                    }
                }
            }
        }
    }

    private func connect() {
        let address = host.trimmingCharacters(in: .whitespacesAndNewlines)
        let pieces = address.split(separator: ".", omittingEmptySubsequences: false)
        guard pieces.count == 4, pieces.allSatisfy({ part in
            !part.isEmpty && part.allSatisfy({ $0.isASCII && $0.isNumber }) &&
            (Int(part).map { (0...255).contains($0) } ?? false)
        }), let number = Int(port), (1...65535).contains(number),
        code.count == 6, code.allSatisfy({ $0.isASCII && $0.isNumber }) else {
            validation = "IPv4、1〜65535のポート、6桁の数字コードを入力してください。"
            return
        }
        // Normalize IPv4 so alternate numeric representations cannot change the origin.
        let canonical = pieces.map { String(Int($0)!) }.joined(separator: ".")
        connection = URL(string: "http://\(canonical):\(number)/phone?code=\(code)")
        validation = ""
    }
}

private struct GameWebView: UIViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator(url: url) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let scripts = configuration.userContentController
        scripts.addUserScript(WKUserScript(source: "window.bulletPetNative=true;", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        scripts.add(WeakGameMessageHandler(context.coordinator), name: "bulletPet")
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = context.coordinator
        web.isOpaque = false
        web.backgroundColor = .black
        web.scrollView.backgroundColor = .black
        context.coordinator.attach(web)
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {}

    static func dismantleUIView(_ web: WKWebView, coordinator: Coordinator) {
        coordinator.shutdown()
        web.stopLoading()
        web.configuration.userContentController.removeScriptMessageHandler(forName: "bulletPet")
        web.navigationDelegate = nil
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        let url: URL
        private weak var web: WKWebView?
        private let motion = CMMotionManager()
        private var neutral: (Double, Double)?
        private var ready = false
        private var observers: [NSObjectProtocol] = []
        private var disposed = false

        init(url: URL) { self.url = url; super.init() }

        func attach(_ web: WKWebView) {
            self.web = web
            UIApplication.shared.isIdleTimerDisabled = UIApplication.shared.applicationState == .active
            let center = NotificationCenter.default
            observers.append(center.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.stopMotion() })
            observers.append(center.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in self?.startMotion() })
            // Restrict subresources too; navigation delegates alone do not cover fetch/scripts.
            let origin = "http://\(url.host!):\(url.port!)"
            let escaped = NSRegularExpression.escapedPattern(for: origin)
            let rules: [[String: Any]] = [
                ["trigger": ["url-filter": ".*"], "action": ["type": "block"]],
                ["trigger": ["url-filter": "^\(escaped)/(phone([?].*)?|assets/[^?]*|api/(input|events|state)([?].*)?)$"], "action": ["type": "ignore-previous-rules"]]
            ]
            guard let data = try? JSONSerialization.data(withJSONObject: rules), let json = String(data: data, encoding: .utf8) else { return }
            WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "BulletPetLAN", encodedContentRuleList: json) { [weak self] list, error in
                DispatchQueue.main.async {
                    guard let self = self, !self.disposed, let web = self.web else { return }
                    guard let list = list, error == nil else { self.showError(); return }
                    web.configuration.userContentController.add(list)
                    web.load(URLRequest(url: self.url, timeoutInterval: 12))
                }
            }
        }

        private func trusted(_ candidate: URL?) -> Bool {
            guard let candidate = candidate else { return false }
            return candidate.scheme == "http" && candidate.host == url.host &&
                (candidate.port ?? 80) == (url.port ?? 80) && candidate.user == nil &&
                candidate.password == nil && candidate.path == "/phone"
        }

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            let allowed = action.targetFrame?.isMainFrame == true && trusted(action.request.url)
            if !allowed { stopMotion() }
            decisionHandler(allowed ? .allow : .cancel)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            let success = (response.response as? HTTPURLResponse).map { (200...299).contains($0.statusCode) } ?? false
            let allowed = response.isForMainFrame && trusted(response.response.url) && success
            decisionHandler(allowed ? .allow : .cancel)
            if !allowed { ready = false; stopMotion(); showError() }
        }

        func webView(_ webView: WKWebView, didReceiveServerRedirectForProvisionalNavigation navigation: WKNavigation!) {
            ready = false
            stopMotion()
            webView.stopLoading()
            showError()
        }
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { ready = false; stopMotion() }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard trusted(webView.url) else { return }
            webView.viewWithTag(8767)?.removeFromSuperview()
            ready = true
            startMotion()
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            if (error as NSError).code != NSURLErrorCancelled { showError() }
        }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { showError() }
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { ready = false; stopMotion(); showError() }

        private func showError() {
            ready = false
            stopMotion()
            guard let web = web else { return }
            let label = UILabel()
            label.tag = 8767
            label.text = "PCに接続できません。\n\nPCのゲーム起動・IPv4・ポート・Wi-Fi・ファイアウォールと、iPhoneのローカルネットワーク許可を確認してください。\n\n上の「接続先へ戻る」から入力を確認して、もう一度開けます。"
            label.numberOfLines = 0
            label.textColor = .white
            label.backgroundColor = UIColor(red: 0.06, green: 0.09, blue: 0.15, alpha: 1)
            label.textAlignment = .center
            label.font = .preferredFont(forTextStyle: .body)
            label.translatesAutoresizingMaskIntoConstraints = false
            web.viewWithTag(8767)?.removeFromSuperview()
            web.addSubview(label)
            NSLayoutConstraint.activate([
                label.leadingAnchor.constraint(equalTo: web.leadingAnchor, constant: 24),
                label.trailingAnchor.constraint(equalTo: web.trailingAnchor, constant: -24),
                label.topAnchor.constraint(equalTo: web.topAnchor),
                label.bottomAnchor.constraint(equalTo: web.bottomAnchor)
            ])
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard ready, message.frameInfo.isMainFrame, trusted(message.frameInfo.request.url),
                let body = message.body as? [String: Any], body["type"] as? String == "recenter" else { return }
            neutral = nil
        }

        private func startMotion() {
            UIApplication.shared.isIdleTimerDisabled = !disposed && UIApplication.shared.applicationState == .active
            guard !disposed, ready, trusted(web?.url), UIApplication.shared.applicationState == .active,
                  !motion.isDeviceMotionActive, motion.isDeviceMotionAvailable else { return }
            neutral = nil
            motion.deviceMotionUpdateInterval = 1.0 / 30.0
            motion.startDeviceMotionUpdates(to: .main) { [weak self] sample, _ in
                guard let self = self, !self.disposed, self.motion.isDeviceMotionActive, self.ready, self.trusted(self.web?.url),
                      UIApplication.shared.applicationState == .active, let gravity = sample?.gravity else { return }
                if self.neutral == nil { self.neutral = (gravity.x, gravity.z) }
                guard let neutral = self.neutral else { return }
                // Portrait upright: X measures left/right; signed Z distinguishes forward/back tilt.
                // Y is near -1 upright and cannot distinguish the two directions.
                let x = max(-1.0, min(1.0, (gravity.x - neutral.0) * 2.0))
                let y = max(-1.0, min(1.0, -(gravity.z - neutral.1) * 2.0))
                self.web?.evaluateJavaScript("window.onNativeMotion&&window.onNativeMotion({tiltX:\(x),tiltY:\(y),active:true})", completionHandler: nil)
            }
        }

        private func stopMotion() {
            UIApplication.shared.isIdleTimerDisabled = false
            motion.stopDeviceMotionUpdates()
            neutral = nil
            if trusted(web?.url) {
                web?.evaluateJavaScript("window.onNativeMotion&&window.onNativeMotion({tiltX:0,tiltY:0,active:false})", completionHandler: nil)
            }
        }

        func shutdown() {
            disposed = true
            stopMotion()
            observers.forEach { NotificationCenter.default.removeObserver($0) }
            observers.removeAll()
        }
        deinit { motion.stopDeviceMotionUpdates(); observers.forEach { NotificationCenter.default.removeObserver($0) } }
    }
}

private final class WeakGameMessageHandler: NSObject, WKScriptMessageHandler {
    private weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(userContentController, didReceive: message)
    }
}
