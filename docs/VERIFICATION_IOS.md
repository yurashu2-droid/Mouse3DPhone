# iOS検証

## 環境の区別

Windowsの作業環境にはSwift、Xcode、iOS SDKがありません。iOSビルドはGitHub ActionsのmacOS runnerで実行します。コンパイル成功は、iPhone実機の計測やBlenderの操作感を検証したこととは区別します。

## 自動検証

- Swift XCTest：JSONの型とwxyz、クラッチ中の掴み保持、計測喪失と復帰、初期解放フレーム、シーケンスとセッションリセット、無効な位置・回転・接続設定。
- Swift executableが生成する13パケットを、同梱のBlender `parse_packet` と `SessionGate` で検証。座標・回転の変換、掴み・クラッチ・復帰・セッション待ち時間を確認。
- IPAパッケージ検証：Payload構造、チェックサム、実行権限、arm64 Mach-O、署名なし。シミュレーターやソースをIPAと誤認しないことを確認。
- Xcode：Info.plist、privacy manifest、project.pbxproj検証、iPhone arm64 Releaseビルド。コード署名なし。

実行結果は [Actions](https://github.com/yurashu2-droid/Mouse3DPhone/actions/workflows/ios-unsigned.yml) の各実行ログを参照してください。

Windowsで実行した確認：元のBlender suite **61件成功**（`python -X utf8 -m pytest -q`）、IPA包装 **5件成功**。元のテストのソース読み込みがWindows標準のcp932では失敗したため、UTF-8モードを使用しました。元のBlenderコードは変更していません。

### 2026-10-06 実行結果

[macOS CI #1](https://github.com/yurashu2-droid/Mouse3DPhone/actions/runs/37454325969) は成功しました。ビルド対象コミット：`61fb0623d2560086218b5fc4e39237a1da74e793`。

- Xcode **16.4**、iPhoneOS SDK **18.5**、iOS下限 **16.0**、arm64 Release、コード署名なし。
- Swift XCTest **7件成功**。Swift生成 **13パケット** と実際のBlenderパーサー／セッションゲートの互換検証成功。
- IPA包装 **5件成功**、plist／プロジェクト検査成功、Xcode **BUILD SUCCEEDED**。
- `SpatialPointer-unsigned.ipa`：**155904 bytes**、アプリバージョン **0.2.0**。
- SHA-256：`475efc1280666959084bcdab88f0e89a7a7822fe03944bf5f81b6b48ddb3f003`。
- Windowsへ成果物をダウンロードし、SHA-256、Payload構造、arm64実行ファイル、署名なし、Info.plistを確認しました。

機能全体の独立レビューを1回実施し、Swiftの小数リテラルとarm64シミュレーターを識別するIPA検査を修正してからCIを実行しました。以下の実機確認は未実施です。

## 実機で確認すること（未実施）

1. 署名してiPhoneへ入れ、カメラ／ローカルネットワークの許可を確認する。
2. Blenderの練習シーンでUDP LAN受信を開始し、アプリからのAccepted件数を確認する。
3. 追従ONで左右10cm、上下、前後をゆっくり動かし、方向とMotion gainを確認する。スマホの回転も確認する。
4. 物体を選択し、掴むボタンの押下中だけ動くことと、指を離す／ボタン外へ滑らせる時の解放を確認する。
5. 掴み中に追従OFFで持ち直し、ONに戻して位置が飛ばないことを確認する。
6. カメラを覆う・暗い場所へ向ける・Wi-Fiを切る・画面を離れる場合に、掴みが解除されることを確認する。復帰しても自動で掴み直さないことを確認する。
7. 計測リセット後、追従OFF、解放状態になり、新しい基準で再開できることを確認する。
8. 小さいiPhone、文字サイズ拡大、ダークモード、VoiceOverで接続設定と操作が可能なことを確認する。

UDPに受信応答はありません。停止パケットは最善努力で、紛失時やiOSのサスペンド時はBlenderの0.75秒タイムアウトで解放します。実機の位置精度・遅延・ジッターは未測定です。
