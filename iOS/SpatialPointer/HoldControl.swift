import SwiftUI
import UIKit

final class HoldButton: UIButton {
    var onHeld: ((Bool) -> Void)?
    var onAccessibleToggle: (() -> Void)?
    private var holding = false

    private func hold(_ value: Bool) {
        guard holding != value else { return }
        holding = value
        onHeld?(value)
    }

    override func beginTracking(_ touch: UITouch, with event: UIEvent?) -> Bool {
        guard isEnabled else { return false }
        hold(true)
        return true
    }

    override func continueTracking(_ touch: UITouch, with event: UIEvent?) -> Bool {
        guard holding else { return false }
        // Leaving the control cancels this press. Re-entry requires a fresh touch.
        if !bounds.insetBy(dx: -16, dy: -16).contains(touch.location(in: self)) {
            hold(false)
            return false
        }
        return true
    }

    override func endTracking(_ touch: UITouch?, with event: UIEvent?) { hold(false) }
    override func cancelTracking(with event: UIEvent?) { hold(false) }

    func synchronize(held: Bool) {
        // Tracking loss can clear app state while the original finger is still down.
        // Continuing that old touch must never create a new hold after recovery.
        if !held { holding = false }
    }

    override var isEnabled: Bool {
        didSet { if !isEnabled { hold(false) } }
    }

    override func accessibilityActivate() -> Bool {
        guard isEnabled else { return false }
        onAccessibleToggle?()
        return true
    }
}

struct HoldControl: UIViewRepresentable {
    enum Kind { case move, grab }
    var kind: Kind
    var enabled: Bool
    var held: Bool
    var onHeld: (Bool) -> Void
    var onAccessibleToggle: () -> Void

    func makeUIView(context: Context) -> HoldButton {
        let button = HoldButton(frame: .zero)
        button.isExclusiveTouch = false
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.accessibilityLabel = kind == .grab ? "選択中の物体を掴んで動かす" : "ポインタだけ動かす"
        button.accessibilityHint = "押している間だけ動きます。VoiceOverではダブルタップで開始／停止を切り替えます。計測が途切れると解除します。"
        return button
    }

    func updateUIView(_ button: HoldButton, context: Context) {
        button.onHeld = onHeld
        button.onAccessibleToggle = onAccessibleToggle
        button.isEnabled = enabled
        button.synchronize(held: held)
        var configuration = UIButton.Configuration.filled()
        configuration.title = kind == .grab ? "掴んで動かす" : "ポインタを動かす"
        configuration.subtitle = held ? "指を離すと停止" : "押している間だけ"
        configuration.image = UIImage(systemName: kind == .grab
                                      ? (held ? "hand.closed.fill" : "hand.draw.fill")
                                      : "move.3d")
        configuration.imagePlacement = .top
        configuration.imagePadding = 12
        configuration.titlePadding = 8
        configuration.cornerStyle = .large
        configuration.baseBackgroundColor = held ? .systemOrange : (kind == .grab ? .systemTeal : .systemIndigo)
        configuration.baseForegroundColor = .white
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 20, leading: 16, bottom: 20, trailing: 16)
        button.configuration = configuration
        button.accessibilityValue = held ? "操作中" : "停止中"
    }
}
