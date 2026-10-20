import ARKit
import SceneKit
import SwiftUI

private struct CameraPreview: UIViewRepresentable {
    let session: ARSession

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.scene = SCNScene()
        view.automaticallyUpdatesLighting = false
        view.backgroundColor = .black
        return view
    }

    func updateUIView(_ view: ARSCNView, context: Context) {}
}

private struct PointerPreviewView: View {
    @ObservedObject var preview: PointerPreview

    var body: some View {
        ZStack {
            Color.black
            if let image = preview.image {
                Image(uiImage: image).resizable().scaledToFit()
                    .accessibilityLabel("3Dポインタの位置から見たBlenderの映像")
            } else {
                VStack(spacing: 10) {
                    Image(systemName: "viewfinder").font(.title)
                    Text(preview.status).font(.footnote).multilineTextAlignment(.center)
                }
                .foregroundStyle(.white).padding(24)
            }
        }
        .overlay(alignment: .topLeading) {
            Text("ポインタ視点").font(.caption.weight(.semibold))
                .padding(8).background(.regularMaterial, in: Capsule()).padding(12)
        }
    }
}

struct ContentView: View {
    @ObservedObject var controller: PhoneController
    @AppStorage("pcIPv4") private var host = ""
    @AppStorage("udpPort") private var port = "5005"
    @AppStorage("translationSensitivity") private var translationSensitivity = 1.0
    @AppStorage("rotationSensitivity") private var rotationSensitivity = 1.0
    @AppStorage("pointerPreviewEnabled") private var previewEnabled = false
    @AppStorage("pointerPreviewPort") private var previewPort = "5006"
    @State private var token = ""
    @State private var showingSettings = false
    @State private var showingHelp = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    camera
                    controls
                    connection
                    if let message = controller.message {
                        Label(message, systemImage: "info.circle")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(20)
            }
            .background(Color(uiColor: .systemGroupedBackground))
            .navigationTitle("Spatial Pointer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { showingHelp = true } label: { Image(systemName: "questionmark.circle") }
                        .accessibilityLabel("使い方")
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        controller.stop()
                        showingSettings = true
                    } label: { Image(systemName: "slider.horizontal.3") }
                        .accessibilityLabel("接続設定")
                }
            }
            .sheet(isPresented: $showingSettings) { settingsView }
            .sheet(isPresented: $showingHelp) { helpView }
            .onChange(of: showingHelp) { visible in if visible { controller.stop() } }
        }
        .tint(.teal)
        .onAppear {
            controller.setSensitivity(translation: translationSensitivity, rotation: rotationSensitivity)
            controller.configurePreview(enabled: previewEnabled, port: previewPort)
        }
        .onChange(of: translationSensitivity) { _ in updateSensitivity() }
        .onChange(of: rotationSensitivity) { _ in updateSensitivity() }
        .onChange(of: previewEnabled) { controller.configurePreview(enabled: $0, port: previewPort) }
        .onChange(of: previewPort) { controller.configurePreview(enabled: previewEnabled, port: $0) }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("手の動きを、3Dの操作に。")
                .font(.title2.weight(.semibold))
            Text("スマホを動かして位置を、傾けて向きを操作します。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private var camera: some View {
        ZStack(alignment: .bottomLeading) {
            CameraPreview(session: controller.session)
                .frame(height: 210)
                .accessibilityHidden(true)
            // Keep the AR view and session mounted underneath the remote image.
            if previewEnabled && controller.isRunning {
                PointerPreviewView(preview: controller.preview)
            }
            if !controller.isRunning {
                VStack(spacing: 10) {
                    Image(systemName: "viewfinder").font(.largeTitle)
                    Text("送信を始めると、カメラで位置を計測します。")
                        .font(.subheadline).multilineTextAlignment(.center)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding(24)
            }
            if controller.isRunning {
                Label(controller.tracked ? "計測中" : "計測準備／一時停止",
                      systemImage: controller.tracked ? "dot.radiowaves.left.and.right" : "pause.circle")
                    .font(.caption.weight(.semibold))
                    .padding(10)
                    .background(.regularMaterial, in: Capsule())
                    .padding(12)
            }
        }
        .frame(height: 210)
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .overlay(alignment: .topTrailing) {
            if controller.isRunning {
                Button { controller.resetTracking() } label: {
                    Image(systemName: "arrow.counterclockwise")
                        .padding(12).background(.regularMaterial, in: Circle())
                }
                .accessibilityLabel("位置計測をやり直す。現在の掴みを解除し、追従を停止します。")
                .padding(12)
            }
        }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label(controller.trackingStatus, systemImage: controller.tracked ? "checkmark.circle.fill" : "viewfinder")
                .font(.subheadline)
                .foregroundStyle(controller.tracked ? Color.teal : Color.secondary)
            HStack(spacing: 12) {
                HoldControl(kind: .move, enabled: controller.canGrab, held: controller.moveHeld,
                            onHeld: { controller.setMoveHeld($0) },
                            onAccessibleToggle: { controller.setMoveHeld(!controller.moveHeld) })
                HoldControl(kind: .grab, enabled: controller.canGrab, held: controller.grabHeld,
                            onHeld: { controller.setGrabHeld($0) },
                            onAccessibleToggle: { controller.setGrabHeld(!controller.grabHeld) })
            }
            .frame(minHeight: 150)
            Text("指を離すとその場で停止し、スマホを持ち直せます。両方を押すと掴みが優先されます。")
                .font(.footnote).foregroundStyle(.secondary)
            sensitivityControls
            Toggle("ポインタ視点を表示", isOn: $previewEnabled)
                .font(.subheadline)
            if previewEnabled {
                Text("BlenderのPhone pointer viewをONにしてください。スマホのカメラによる位置計測は継続します。")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func updateSensitivity() {
        controller.setSensitivity(translation: translationSensitivity, rotation: rotationSensitivity)
    }

    private var sensitivityControls: some View {
        VStack(spacing: 12) {
            sensitivitySlider("移動の感度", value: $translationSensitivity)
            sensitivitySlider("回転の感度", value: $rotationSensitivity)
        }
        .padding(16)
        .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18))
    }

    private func sensitivitySlider(_ title: String, value: Binding<Double>) -> some View {
        VStack(spacing: 4) {
            HStack {
                Text(title).font(.subheadline)
                Spacer()
                Text(String(format: "%.1f×", value.wrappedValue)).font(.subheadline.monospacedDigit())
            }
            Slider(value: value, in: 0.1...5, step: 0.1) { Text(title) }
                .accessibilityValue(String(format: "%.1f倍", value.wrappedValue))
        }
    }

    private var connection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(controller.networkStatus, systemImage: "wifi")
                    .font(.subheadline.weight(.medium))
                Spacer()
                if controller.isRunning {
                    Text("\(controller.sentCount) 件").font(.caption.monospacedDigit())
                }
            }
            if !host.isEmpty {
                Text("送信先 \(host):\(port)")
                    .font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Button {
                if controller.isRunning {
                    controller.stop()
                } else if host.isEmpty || token.isEmpty {
                    showingSettings = true
                } else {
                    controller.start(host: host, port: port, token: token)
                }
            } label: {
                Text(controller.isStarting ? "準備中…" : controller.isRunning ? "送信を停止" : "送信を開始")
                    .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6)
            }
            .buttonStyle(.borderedProminent)
            .disabled(controller.isStarting)
            Text("件数はスマホ側の送信数です。BlenderのAccepted件数と動きを確認してください。")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(18)
        .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 22))
    }

    private var settingsView: some View {
        NavigationStack {
            Form {
                Section("Blenderの接続先") {
                    TextField("PCのIPv4（例：192.168.1.12）", text: $host)
                        .keyboardType(.decimalPad)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .accessibilityLabel("PCのIPv4アドレス")
                    TextField("UDPポート", text: $port).keyboardType(.numberPad)
                        .accessibilityLabel("UDPポート")
                    TextField("視点HTTPポート", text: $previewPort).keyboardType(.numberPad)
                        .accessibilityLabel("ポインタ視点のHTTPポート")
                    SecureField("Blenderに表示されたトークン", text: $token)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .accessibilityLabel("BlenderのLAN用トークン")
                }
                Section {
                    Picker("送信頻度", selection: $controller.sendHz) {
                        Text("30回／秒").tag(30)
                        Text("60回／秒").tag(60)
                    }
                }
                Section("接続の準備") {
                    Text("1. PCとiPhoneを同じWi-Fi、またはUSBテザリングで接続します。\n2. BlenderのSpatialタブでAllow LAN devicesをONにします。\n3. Start UDP Receiverを押し、接続に使うPCのIPv4・ポート・トークンをここに入力します。")
                    Text("PCのファイアウォールで、BlenderのUDPポートへの受信を許可してください。ポインタ視点を使う場合は、HTTPポート（標準5006／TCP）も許可します。トークンはアプリを終了すると消えます。")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("USBテザリングの準備") {
                    Text("iPhoneの設定で「インターネット共有 → ほかの人の接続を許可」をONにし、USBでPCに接続して「信頼」を選びます。WindowsにはAppleデバイスまたはiTunesが必要です。")
                    Text("PCのUSBテザリング用アダプターのIPv4を入力してください。Wi-Fi接続時とは送信先IPが変わります。ケーブルをつなぐだけでは通信できません。")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                if let message = controller.message {
                    Section { Text(message).foregroundStyle(.red) }
                }
            }
            .navigationTitle("接続設定")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("閉じる") { showingSettings = false }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("送信開始") {
                        controller.start(host: host, port: port, token: token)
                        if controller.isRunning || controller.isStarting { showingSettings = false }
                    }
                    .disabled(controller.isStarting)
                }
            }
        }
    }

    private var helpView: some View {
        NavigationStack {
            List {
                Section("操作の順番") {
                    Text("1. Blenderで練習シーンを開き、動かしたい物体を選択します。")
                    Text("2. 接続設定を入力して送信を開始します。明るく、模様のある周囲にカメラを向けます。")
                    Text("3. 「ポインタを動かす」を押したまま、スマホを動かします。物体を選ばずにポインタだけ操作できます。")
                    Text("4. 「掴んで動かす」を押したままスマホを動かすと、選択中の物体も移動・回転します。指を離すと物体を置きます。")
                }
                Section("持ち直しと計測のやり直し") {
                    Text("両方のボタンから指を離すと、その場で停止します。スマホを持ち直して押し直しても、ポインタの位置は飛びません。")
                    Text("両方を押している間は掴みが優先されます。ポインタ移動を押したまま掴みだけ離すと、物体を置いてポインタの移動を続けます。")
                    Text("カメラ欄の矢印で位置計測をやり直せます。計測の中断や通信停止では両方の操作を解除します。復帰後は指を離して押し直してください。画面を離れると送信も停止します。")
                }
                Section("感度とポインタ視点") {
                    Text("移動と回転の感度はスマホで個別に調整でき、次回も保存されます。BlenderのMotion gainは移動に追加で掛かります。")
                    Text("BlenderでPhone pointer viewをONにし、スマホで「ポインタ視点を表示」をONにします。視点HTTPポートと接続トークンを合わせてください。")
                    Text("ポインタ位置から前方を見る映像です。物体の内部に入ると視界が遮られることがあります。表示中も周囲にカメラを向けて位置計測を続けてください。")
                }
                Section("対応する操作") {
                    Text("BlenderのObject Modeで、選択中の物体を移動・回転します。表面への自動選択とスカルプトは未対応です。")
                    Text("画面の向きとの位置合わせはまだありません。まずBlenderのMotion gainを小さめにして確認してください。")
                }
            }
            .navigationTitle("使い方")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("閉じる") { showingHelp = false } } }
        }
    }
}
