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

struct ContentView: View {
    @ObservedObject var controller: PhoneController
    @AppStorage("pcIPv4") private var host = ""
    @AppStorage("udpPort") private var port = "5005"
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
            Button {
                controller.setFollow(!controller.following)
            } label: {
                HStack {
                    Image(systemName: controller.following ? "pause.fill" : "play.fill")
                    Text(controller.following ? "追従中 · タップで持ち直し" : "追従を開始")
                    Spacer()
                    Text(controller.following ? "ON" : "OFF").font(.caption.weight(.bold))
                }
                .padding(16)
                .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18))
            }
            .disabled(!controller.isRunning)
            .accessibilityHint("追従を止めても、掴んでいる物体は保持します。再開時に位置が飛ぶのを防ぎます。")

            HoldControl(enabled: controller.canGrab, held: controller.grabbing,
                        onHeld: { controller.setGrab($0) },
                        onAccessibleToggle: { controller.setGrab(!controller.grabbing) })
                .frame(minHeight: 150)
            Text(controller.following ? "カメラを周囲に向けたまま、ゆっくり動かしてください。"
                 : "持ち直す時は追従OFF。元の位置に戻さず、再開できます。")
                .font(.footnote).foregroundStyle(.secondary)
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
                    Text("1. PCとiPhoneを同じWi-Fiに接続します。\n2. BlenderのSpatialタブでAllow LAN devicesをONにします。\n3. Start UDP Receiverを押し、PCのIPv4・ポート・トークンをここに入力します。")
                    Text("PCのファイアウォールはプライベートネットワークの受信を許可してください。トークンはアプリを終了すると消えます。")
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
                    Text("3. 「追従を開始」を押します。スマホの移動と回転が3Dポインタに反映されます。")
                    Text("4. 「掴む」を押したままスマホを動かします。指を離すと物体を置きます。")
                }
                Section("持ち直しと計測のやり直し") {
                    Text("追従OFFでポインタを止め、スマホを持ち直してから追従ONにします。掴み中でも利用できます。")
                    Text("カメラ欄の矢印で位置計測をやり直せます。掴みは解除され、追従OFFに戻ります。")
                    Text("計測が途切れた後は、掴むボタンから指を離して押し直してください。画面を離れると送信も停止します。")
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
