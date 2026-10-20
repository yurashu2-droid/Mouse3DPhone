# Mouse3DPhone / Spatial Pointer

iPhoneの位置・回転でBlenderの3Dポインタを操作する、iOSネイティブアプリです。カメラとモーションセンサーを使うARKitの空間計測を利用します。スマホを傾けるだけの操作ではなく、左右・上下・前後の移動を送信します。

0.3.0では、スマホ側で移動と回転の感度を別々に調整できます。操作は「ポインター移動」と「掴んで移動」の2つの押しボタンにまとめました。Blenderアドオン0.2.0と組み合わせると、ポインター位置から見た景色をスマホに表示できます。

## 無署名IPAを入手する

このリポジトリの [Actions](https://github.com/yurashu2-droid/Mouse3DPhone/actions/workflows/ios-unsigned.yml) を開き、成功した **Build unsigned iOS IPA** の実行を選びます。

下部の **Artifacts → SpatialPointer-unsigned-ipa** をダウンロードして解凍してください。

- `SpatialPointer-unsigned.ipa`：無署名のiPhone arm64アプリ
- `SpatialPointer-unsigned.ipa.sha256`：SHA-256チェックサム
- `spatial_pointer-0.2.0.zip`：更新版のBlenderアドオン（ZIPのままインストール）
- `spatial_pointer-0.2.0.zip.sha256`：アドオンのSHA-256チェックサム

Actionsの成果物ダウンロードにはGitHubへのログインが必要です。成果物の保存期間は30日です。期限切れの場合は **Run workflow** で再ビルドできます。

通常のiPhoneにインストールする際は、使用するサイドロードツールで署名してください。無署名は「ビルド時にApple IDや証明書を使用しない」という意味です。署名なしで通常のiOSへ直接インストールできることを意味しません。

**対応：iOS 16以降、ARKitのWorld Trackingに対応するiPhone。** シミュレーターでは実際の位置計測はできません。

## Blenderを準備する

1. Actionsの成果物から **spatial_pointer-0.2.0.zip** を保存します。ZIPは解凍せず、Blenderの **Preferences → Add-ons → Install from Disk** でインストールします。旧版が入っている場合は、受信を停止してアドオンを更新してください。
2. 3Dビューで `N` → **Spatial** を開きます。
3. **Open Practice Scene** を開き、動かしたい物体を通常のマウスで選択します。
4. **Allow LAN devices** をONにします。Blenderの **Allow Online Access** もONにします。
5. **Start UDP Receiver** を押し、ポートと生成された **Pairing Token** を確認します。
6. PCとiPhoneを同じ信頼できるWi-Fi／LAN、またはUSBテザリングで接続します。PCのファイアウォールでは、BlenderのUDPポート（初期値5005）への受信を使用中のネットワークで許可します。

Windowsでは `ipconfig` の、使用中のWi-FiまたはEthernetアダプターの **IPv4アドレス** を確認します。`127.0.0.1` はiPhoneからPCを指すアドレスではありません。

### USBテザリングで接続する（0.2.1以降）

社寮などの共用Wi-Fiで端末間通信が禁止されている場合は、USBテザリングの経路で試せます。

1. Windowsに **Appleデバイス** または **iTunes** をインストールします。
2. iPhoneの **設定 → インターネット共有 → ほかの人の接続を許可** をONにします。
3. iPhoneをデータ通信対応のUSBケーブルでPCに接続し、表示されたら **信頼** を選びます。
4. PCの `ipconfig` で、USBテザリング用アダプターのIPv4を確認してアプリの送信先に入力します。Wi-Fi接続時のPCのIPとは異なります。
5. BlenderのAllow LAN devices、UDPポート、トークンは同じように設定し、アプリで送信を開始します。

[AppleのUSBテザリング手順](https://support.apple.com/ja-jp/111785)。アプリはiOSが選ぶ送信先への経路を使用します。ケーブルを挿すだけでデータを転送する方式ではありません。USB経由の実機動作は未検証なので、BlenderのAccepted件数と実際の動きを確認してください。

## iPhoneで操作する

1. **接続設定** にPCのIPv4、UDPポート（初期値5005）、Blenderのトークンを入力します。
2. **送信開始** を押し、カメラとローカルネットワークのアクセスを許可します。
3. 明るく、模様のある周囲にカメラを向け、位置計測が安定するまで少しゆっくり動かします。
4. **ポインター移動** を押している間、スマホの移動・回転を3Dポインタへ反映します。物体の選択は不要です。指を離すとその場で停止するので、スマホを持ち直せます。
5. 物体を動かす場合はBlenderで対象を選択し、**掴んで移動** を押したままスマホを動かします。指を離すと物体を置きます。
6. スマホの感度設定で **移動** と **回転** を別々に調整します。初期値はそれぞれ1倍です。BlenderのMotion gainは追加の移動倍率なので、まず1で試してください。

VoiceOverでは掴むボタンのダブルタップで掴み／解放を切り替えます。計測が途切れると掴みを解除し、復帰後も自動で掴み直しません。再度ボタンを操作してください。

### スマホでポインター視点を見る

1. BlenderのUDP受信を開始し、**Phone pointer view** をONにします。映像用HTTPポートの初期値は **5006** です。
2. iPhoneで送信を開始し、**ポインター視点** を有効にします。映像ポートとPairing TokenをBlender側に合わせます。
3. ポインターの位置・向きに応じた景色を、最大5fpsのプレビューで表示します。PCのビューポートとシーンカメラは変更しません。

映像表示中もiPhoneのカメラによる位置計測を続けます。カメラを覆わず、明るく模様のある場所で操作してください。ポインターが物体の内部に入ると視界が遮られる場合があります。映像はLAN内HTTPで送り、UDPと同じトークンを照合します。Windowsで映像だけ届かない場合は、使用中ネットワークでBlenderのTCP 5006受信許可も確認してください。

画面を離れると送信を停止します。カメラ欄の矢印は位置計測をやり直し、掴みを解除して追従OFFへ戻します。PCのIPv4・ポートは保存しますが、トークンはアプリを終了すると消えます。

**「UDP送信可能」「送信件数」は、Blenderとの接続確認ではありません。** 既存プロトコルに応答がないため、BlenderのAccepted件数と実際の動きを確認してください。接続・位置計測のリセット直後は、受信側のセッション切り替えのため約0.85秒待ってから送信します。

## 現在の機能と制限

- 物体を選択せずに3Dポインタを移動・回転。別ボタンで選択中の物体を掴んで移動。
- 移動／回転の独立感度調整、30／60回毎秒のUDP送信、任意のポインター視点プレビュー。
- 計測が不安定／途切れた時はポインタを固定し、掴みを解除。
- iPhoneのカメラ画像は送信・保存しません。iPhoneから送るのは位置・回転、ボタン状態、セッション番号とトークンだけです。プレビューON時はBlenderの描画画像をPCからiPhoneへ送り、ディスクへは保存しません。
- BlenderのObject Mode専用。表面への自動選択・スカルプトは未実装です。
- ARKitの座標をBlender座標へ変換しますが、物理モニターの向きとのキャリブレーションは未実装です。
- LAN内UDPの実験用です。トークンは平文で送信されます。

## Macで無署名ビルドする

Xcode 16以降とiOS SDK、Python 3が必要です。追加のiOSライブラリは不要です。

```bash
swift test --package-path iOS/SpatialPointerCore
swift run --package-path iOS/SpatialPointerCore PacketFixture > /tmp/spatial-pointer-fixtures.json
python3 tools/check_wire.py /tmp/spatial-pointer-fixtures.json
bash tools/build_unsigned.sh
```

出力は `dist/SpatialPointer-unsigned.ipa` です。コード署名を無効にしてiPhone arm64用にビルドし、実際のMach-Oと署名の有無を検査してからIPAへ格納します。

Xcodeで開く場合は `iOS/SpatialPointer.xcodeproj`、Schemeは **SpatialPointer** です。Xcodeから署名して実機へ入れる場合はSigning & CapabilitiesでTeamを選び、必要ならBundle Identifierを変更してください。

## 構成

| パス | 内容 |
|---|---|
| `iOS/SpatialPointer/` | iPhone画面・ARKit・UDP送信 |
| `iOS/SpatialPointerCore/` | 通信仕様・掴み／追従状態・Swiftテスト |
| `blender/` | 元のBlenderアドオン、インストールZIP、テスト |
| `tools/` | 無署名ビルド・IPA検査・Swift→Blender互換検証 |
| `.github/workflows/ios-unsigned.yml` | macOSでテスト・ビルド・IPAを保存 |

Swiftファイルを追加した場合は `python3 tools/generate_xcode_project.py` でXcodeプロジェクトを再生成します。

[検証状況と実機確認の手順](docs/VERIFICATION_IOS.md) · [通信仕様](blender/docs/PROTOCOL.md) · [Blenderの操作説明](blender/README_JA.md)

ライセンス：GPL-3.0-or-later。元のBlenderアドオンと同じ条件を使用します。[LICENSE](LICENSE)
