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
        // Leaving the control cancels this press. Re-entry requires a fresh touch.
        if !bounds.insetBy(dx: -16, dy: -16).contains(touch.location(in: self)) {
            hold(false)
            return false
        }
        return true
    }

    override func endTracking(_ touch: UITouch?, with event: UIEvent?) { hold(false) }
    override func cancelTracking(with event: UIEvent?) { hold(false) }

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
    var enabled: Bool
    var held: Bool
    var onHeld: (Bool) -> Void
    var onAccessibleToggle: () -> Void

    func makeUIView(context: Context) -> HoldButton {
        let button = HoldButton(frame: .zero)
        button.isExclusiveTouch = false
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.accessibilityLabel = "選択中の物体を掴む"
        button.accessibilityHint = "通常は押している間だけ掴みます。VoiceOverではダブルタップで掴む／離すを切り替えます。"
        return button
    }

    func updateUIView(_ button: HoldButton, context: Context) {
        button.onHeld = onHeld
        button.onAccessibleToggle = onAccessibleToggle
        button.isEnabled = enabled
        var configuration = UIButton.Configuration.filled()
        configuration.title = held ? "掴んでいます" : "掴む"
        configuration.subtitle = held ? "指を離すと、その場に置きます" : "押している間だけ · 先にBlenderで物体を選択"
        configuration.image = UIImage(systemName: held ? "hand.closed.fill" : "hand.draw.fill")
        configuration.imagePlacement = .top
        configuration.imagePadding = 12
        configuration.titlePadding = 8
        configuration.cornerStyle = .large
        configuration.baseBackgroundColor = held ? .systemOrange : .systemTeal
        configuration.baseForegroundColor = .white
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 20, leading: 16, bottom: 20, trailing: 16)
        button.configuration = configuration
        button.accessibilityValue = held ? "掴み中" : "解放中"
    }
}
