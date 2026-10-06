import SwiftUI

@main
struct SpatialPointerApp: App {
    @StateObject private var controller = PhoneController()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView(controller: controller)
                .onChange(of: scenePhase) { phase in
                    if phase != .active && controller.isRunning {
                        controller.stop(message: "画面を離れたため停止しました。")
                    } else if phase == .background && controller.isStarting {
                        controller.stop(message: "停止しました。")
                    }
                }
        }
    }
}
