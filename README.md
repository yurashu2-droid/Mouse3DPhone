# Mouse3DPhone / Spatial Pointer

iPhoneの位置・回転でBlenderの3Dポインタを操作する、iOSネイティブアプリです。カメラとモーションセンサーを使うARKitの空間計測を利用します。スマホを傾けるだけの操作ではなく、左右・上下・前後の移動を送信します。

## 無署名IPAを入手する

このリポジトリの [Actions](https://github.com/yurashu2-droid/Mouse3DPhone/actions/workflows/ios-unsigned.yml) を開き、成功した **Build unsigned iOS IPA** の実行を選びます。

下部の **Artifacts → SpatialPointer-unsigned-ipa** をダウンロードして解凍してください。

- `SpatialPointer-unsigned.ipa`：無署名のiPhone arm64アプリ
- `SpatialPointer-unsigned.ipa.sha256`：SHA-256チェックサム

Actionsの成果物ダウンロードにはGitHubへのログインが必要です。成果物の保存期間は30日です。期限切れの場合は **Run workflow** で再ビルドできます。

通常のiPhoneにインストールする際は、使用するサイドロードツールで署名してください。無署名は「ビルド時にApple IDや証明書を使用しない」という意味です。署名なしで通常のiOSへ直接インストールできることを意味しません。

**対応：iOS 16以降、ARKitのWorld Trackingに対応するiPhone。** シミュレーターでは実際の位置計測はできません。

## Blenderを準備する

1. [Blender用アドオンZIP](blender/Install/spatial_pointer-0.1.1.zip) を保存します。ZIPは解凍せず、Blenderの **Preferences → Add-ons → Install from Disk** でインストールします。
2. 3Dビューで `N` → **Spatial** を開きます。
3. **Open Practice Scene** を開き、動かしたい物体を通常のマウスで選択します。
4. **Allow LAN devices** をONにします。Blenderの **Allow Online Access** もONにします。
5. **Start UDP Receiver** を押し、ポートと生成された **Pairing Token** を確認します。
6. PCとiPhoneを同じ信頼できるWi-Fi／LANに接続します。PCのファイアウォールではプライベートネットワークのUDP受信を許可します。

Windowsでは `ipconfig` の、使用中のWi-FiまたはEthernetアダプターの **IPv4アドレス** を確認します。`127.0.0.1` はiPhoneからPCを指すアドレスではありません。

## iPhoneで操作する

1. **接続設定** にPCのIPv4、UDPポート（初期値5005）、Blenderのトークンを入力します。
2. **送信開始** を押し、カメラとローカルネットワークのアクセスを許可します。
3. 明るく、模様のある周囲にカメラを向け、位置計測が安定するまで少しゆっくり動かします。
4. **追従を開始** を押します。スマホの移動・回転をBlenderのポインタへ反映します。
5. **掴む** を押したままスマホを動かします。指を離すと物体を置きます。
6. 持ち直す時は **追従OFF → スマホを持ち直す → 追従ON**。掴み中にも使えます。

VoiceOverでは掴むボタンのダブルタップで掴み／解放を切り替えます。計測が途切れると掴みを解除し、復帰後も自動で掴み直しません。再度ボタンを操作してください。

画面を離れると送信を停止します。カメラ欄の矢印は位置計測をやり直し、掴みを解除して追従OFFへ戻します。PCのIPv4・ポートは保存しますが、トークンはアプリを終了すると消えます。

**「UDP送信可能」「送信件数」は、Blenderとの接続確認ではありません。** 既存プロトコルに応答がないため、BlenderのAccepted件数と実際の動きを確認してください。接続・位置計測のリセット直後は、受信側のセッション切り替えのため約0.85秒待ってから送信します。

## 現在の機能と制限

- 選択中の物体の移動・回転、追従の持ち直し、30／60回毎秒の送信。
- 計測が不安定／途切れた時はポインタを固定し、掴みを解除。
- 画像は送信・保存しません。送るのは位置・回転、ボタン状態、セッション番号とトークンだけです。
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
