import ARKit
import AVFoundation
import Combine
import Foundation
import QuartzCore
import UIKit
import simd

/// ARSession.delegateQueue, UI actions, timer and Network callbacks all use main.
final class PhoneController: NSObject, ObservableObject, ARSessionDelegate {
    let session = ARSession()
    @Published private(set) var isRunning = false
    @Published private(set) var isStarting = false
    @Published private(set) var canGrab = false
    @Published private(set) var grabbing = false
    @Published private(set) var following = false
    @Published private(set) var tracked = false
    @Published private(set) var networkStatus = "未送信"
    @Published private(set) var trackingStatus = "送信開始後、周囲にカメラを向けてください。"
    @Published private(set) var sentCount = 0
    @Published private(set) var poseText = "X 0.00  Y 0.00  Z 0.00 m"
    @Published var message: String?
    @Published var sendHz = 60
    private var state = SenderState()
    private var transport: UDPTransport?
    private var settings: ConnectionSettings?
    private var timer: Timer?
    private var lastFrameTime: Double = -.infinity
    private var lastUIUpdate = 0.0
    private var notBefore = 0.0
    private var interrupted = false
    private var startOperation = UUID()

    override init() {
        super.init()
        session.delegateQueue = .main
        session.delegate = self
    }

    func start(host: String, port: String, token: String) {
        guard !isRunning && !isStarting else { return }
        guard ARWorldTrackingConfiguration.isSupported else {
            message = "この端末はARKitの位置計測に対応していません。iPhone実機で使用してください。"
            return
        }
        let settings: ConnectionSettings
        do { settings = try ConnectionSettings(host: host, port: port, token: token) }
        catch { message = error.localizedDescription; return }
        isStarting = true
        message = nil
        let operation = UUID()
        startOperation = operation
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: begin(settings, operation: operation)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
                DispatchQueue.main.async {
                    guard let self, self.startOperation == operation else { return }
                    if allowed { self.begin(settings, operation: operation) }
                    else { self.cameraDenied() }
                }
            }
        default: cameraDenied()
        }
    }

    private func cameraDenied() {
        isStarting = false
        message = "位置計測にはカメラが必要です。iPhoneの設定でSpatial Pointerのカメラを許可してください。"
    }

    private func begin(_ settings: ConnectionSettings, operation: UUID) {
        guard startOperation == operation else { return }
        self.settings = settings
        state.reset()
        lastFrameTime = -.infinity
        interrupted = false
        notBefore = CACurrentMediaTime() + 0.85
        isStarting = false
        isRunning = true
        networkStatus = "Wi-Fi接続を準備中"
        sentCount = 0
        UIApplication.shared.isIdleTimerDisabled = true
        let transport = UDPTransport()
        self.transport = transport
        transport.onStatus = { [weak self, weak transport] status in
            guard let self, let transport, self.transport === transport, self.isRunning else { return }
            switch status {
            case .ready:
                self.networkStatus = "UDP送信可能 · 受信未確認"
                self.notBefore = CACurrentMediaTime() + 0.85
                self.state.update(pose: self.state.pose, tracked: false)
            case .waiting:
                self.networkStatus = "Wi-Fi／ローカルネットワーク許可を確認"
                self.state.update(pose: self.state.pose, tracked: false)
            case .failed(let error):
                self.stop(message: "通信エラー：\(error)")
            }
            self.publish()
        }
        transport.start(settings)
        runWorldTracking()
        let timer = Timer(timeInterval: 1.0 / Double(sendHz == 30 ? 30 : 60), repeats: true) { [weak self] _ in
            self?.tick()
        }
        self.timer = timer
        RunLoop.main.add(timer, forMode: .common)
        publish()
    }

    private func runWorldTracking() {
        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        configuration.isLightEstimationEnabled = false
        session.delegate = self
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        trackingStatus = "計測準備中。周囲の模様がある場所にカメラを向けてください。"
    }

    func resetTracking() {
        guard isRunning else { return }
        // Release the old session before changing its world / identity.
        state.stop()
        emit(force: true)
        state.reset()
        lastFrameTime = -.infinity
        notBefore = CACurrentMediaTime() + 0.85
        interrupted = false
        runWorldTracking()
        publish()
    }

    func setFollow(_ value: Bool) {
        guard isRunning else { return }
        state.setFollow(value)
        emit()
        publish()
        UISelectionFeedbackGenerator().selectionChanged()
    }

    func setGrab(_ value: Bool) {
        if value && !canGrab { return }
        state.setGrab(value)
        emit()
        publish()
        if value && state.grabbing { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    }

    func stop(message: String? = nil) {
        startOperation = UUID()
        timer?.invalidate()
        timer = nil
        state.stop()
        let final = settings.flatMap { try? state.nextPacket(token: $0.token).encoded() }
        transport?.stop(finalPacket: final)
        transport = nil
        settings = nil
        session.pause()
        isRunning = false
        isStarting = false
        UIApplication.shared.isIdleTimerDisabled = false
        networkStatus = "停止中"
        trackingStatus = "位置計測は停止しています。"
        if let message { self.message = message }
        publish()
    }

    private func tick() {
        guard isRunning else { return }
        let now = CACurrentMediaTime()
        if now - lastFrameTime > 0.25 {
            state.update(pose: state.pose, tracked: false)
            if trackingStatus != "位置情報が途切れました。掴みを解除しています。" {
                trackingStatus = "位置情報が途切れました。掴みを解除しています。"
            }
        }
        emit()
        publish()
        if now - lastUIUpdate >= 0.15 {
            lastUIUpdate = now
            sentCount = transport?.sentCount ?? sentCount
            poseText = String(format: "X %.2f  Y %.2f  Z %.2f m", state.pose.position[0],
                              state.pose.position[1], state.pose.position[2])
        }
    }

    private func emit(force: Bool = false) {
        guard isRunning, let transport, transport.canSend, let settings,
              force || CACurrentMediaTime() >= notBefore else { return }
        do { transport.send(try state.nextPacket(token: settings.token).encoded()) }
        catch { stop(message: "送信データを作れませんでした：\(error.localizedDescription)") }
    }

    private func publish() {
        let readyToGrab = isRunning && transport?.ready == true && state.canGrab
            && CACurrentMediaTime() >= notBefore && CACurrentMediaTime() - lastFrameTime <= 0.25
        if canGrab != readyToGrab { canGrab = readyToGrab }
        if grabbing != state.grabbing { grabbing = state.grabbing }
        if following != state.following { following = state.following }
        if tracked != state.tracked { tracked = state.tracked }
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard isRunning else { return }
        let transform = frame.camera.transform
        let position = transform.columns.3
        let quaternion = simd_quatf(transform)
        guard let pose = try? PhonePose(position: [Double(position.x), Double(position.y), Double(position.z)],
                                      rotation: [Double(quaternion.real), Double(quaternion.imag.x),
                                                 Double(quaternion.imag.y), Double(quaternion.imag.z)]) else {
            state.update(pose: state.pose, tracked: false)
            publish()
            return
        }
        lastFrameTime = CACurrentMediaTime()
        let normal: Bool
        let status: String
        switch frame.camera.trackingState {
        case .normal:
            normal = !interrupted
            status = interrupted ? "計測が中断されています。" : "位置・回転を計測中"
        case .notAvailable:
            normal = false
            status = "位置を計測できません。掴みを解除しています。"
        case .limited(let reason):
            normal = false
            switch reason {
            case .initializing: status = "計測準備中。カメラをゆっくり動かしてください。"
            case .excessiveMotion: status = "動きが速すぎます。ゆっくり動かしてください。"
            case .insufficientFeatures: status = "模様のある明るい場所にカメラを向けてください。"
            case .relocalizing: status = "位置を再確認中。掴みを解除しています。"
            @unknown default: status = "計測が不安定です。掴みを解除しています。"
            }
        }
        let wasTracked = state.tracked
        state.update(pose: pose, tracked: normal)
        if trackingStatus != status { trackingStatus = status }
        if wasTracked && !normal { emit(force: true) }
        publish()
    }

    func sessionWasInterrupted(_ session: ARSession) {
        interrupted = true
        state.update(pose: state.pose, tracked: false)
        trackingStatus = "計測が中断されました。掴みを解除しています。"
        emit(force: true)
        publish()
    }

    func sessionInterruptionEnded(_ session: ARSession) { resetTracking() }

    func session(_ session: ARSession, didFailWithError error: Error) {
        stop(message: "位置計測エラー：\(error.localizedDescription)")
    }
}
