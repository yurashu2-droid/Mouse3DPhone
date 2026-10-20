# Mouse3DPhone 引き継ぎ

記録日：2026-10-20（日本時間）。他のAI・別PCでも、このリポジトリをcloneして本書から作業を再開できます。会話履歴やCodex専用機能は必須ではありません。

## 現在地

- リポジトリ：https://github.com/yurashu2-droid/Mouse3DPhone
- 現在の機能コードは `main` の `f89dd0343392a9a707fbb996984a91734323172c`。
- iOSアプリ **0.3.0 / build 3**、Blender拡張 **0.2.0**。無署名IPAと拡張ZIPを生成済み。
- 成功CI：[run 39433719350](https://github.com/yurashu2-droid/Mouse3DPhone/actions/runs/39433719350)。成果物名 `SpatialPointer-unsigned-ipa` にIPA・拡張ZIP・各SHA-256が入る。成果物保存は30日。期限切れなら同workflowを再実行する。
- 旧版アプリでは、ユーザー本人がWi-Fi経由でBlenderの物体が動くことを確認済み。**新しい0.3.0の2ボタン・感度・スマホ映像表示の実機確認はまだ報告されていない。** 次はその操作感を確認する段階。
- `docs/implementation-progress.md` は初期開発時の履歴。本書と矛盾する「空のリポジトリ」「7テスト」などは現在の状態ではない。

## ユーザーの意図と確定仕様

iPhoneを空間マウスとして使い、ARKitで計測した位置・姿勢をBlenderの既存3Dポインターに反映する。ユーザーの「カーソル」はOSマウスやBlender標準3D Cursorではなく、この拡張の3Dポインターを指す。

- スマホに「ポインタを動かす」「掴んで動かす」の2つの押している間だけ動作するボタン。
- 前者はポインターだけ、後者はポインターとBlenderで選択済みの物体を移動・回転。物体の自動選択は未実装。
- 両方を離すと停止。持ち直して押し直しても位置を飛ばさない。両方を押した場合は掴み優先。移動を押し続け、掴みだけ離すと物体を置いてポインター移動を続ける。
- 移動・回転感度をスマホで別々に0.1〜5倍（初期値1）へ調整し保存。感度変更でも位置・姿勢を飛ばさない。Blender側Motion gainは追加の移動倍率。
- スマホに表示する映像は、**ポインター位置から前方を見た景色**。PC画面の転送やスマホのカメラ映像転送ではない。
- 映像は任意ON、480×270、最大5fps。ARKit計測を継続するためカメラビューを破棄しない。

## コードの案内

| 場所 | 役割 |
| --- | --- |
| `iOS/SpatialPointer/ContentView.swift` | 画面、感度保存、設定、映像切替 |
| `iOS/SpatialPointer/HoldControl.swift` | 押下・解放とアクセシビリティ |
| `iOS/SpatialPointer/Controller.swift` | ARKit、ボタン状態、送信・停止の統合 |
| `iOS/SpatialPointer/UDPTransport.swift` | Network.frameworkのUDP送信。Wi-Fi固定はせずOSの経路選択を使う |
| `iOS/SpatialPointer/PointerPreview.swift` | 同じPCへの認証付きHTTPポーリング、表示画像。1要求ずつ、リダイレクト拒否 |
| `iOS/SpatialPointerCore/` | Swift Package。プロトコル、送信状態、相対移動・回転感度、テスト、互換fixture |
| `blender/spatial_pointer/core.py` | Blender非依存のパーサー、セッション判定、座標変換 |
| `blender/spatial_pointer/runtime.py` | UDP・ポーズ更新・掴み・プレビューのライフサイクル |
| `blender/spatial_pointer/addon.py` | Spatialパネル、設定、オペレーター |
| `blender/spatial_pointer/preview.py` | メインスレッドでGPUOffScreen描画、視点変換、リソース解放 |
| `blender/spatial_pointer/preview_transport.py` | bpy非依存のPNG生成、スナップショット共有、HTTPサーバー |
| `tools/` | Xcodeプロジェクト生成、IPA検証・包装、拡張ZIP生成、単独UDP診断 |
| `.github/workflows/ios-unsigned.yml` | macOSでSwift検証・IPAビルド・拡張包装 |

## 通信と操作の注意

- UDP標準 **5005**。v1 JSON、クォータニオン **wxyz**、ARKit空間。既存形式を維持している。詳細は `blender/spatial_pointer/PROTOCOL.md`。
- 映像HTTP標準 **5006/TCP**。`GET /status` と `/frame.png`、`Authorization: Bearer <Pairing Token>`。URL・ログへトークンを出さない。
- LAN受信にはSpatialの **Allow LAN devices** とBlenderの **Allow Online Access** が必要。同じトークンをスマホに入力する。
- スマホ送信件数は受信確認ではない。UDPにACKはなく、BlenderのAcceptedと実際の動きを確認する。
- 動かない場合は、Accepted/Drop、トークン、Blender側の追従設定、スマホの押下状態、ARKit trackingを順に確認。前回はトークン不一致と旧アプリの追従OFFが原因だった。社寮Wi-Fiや多重ルーターが原因と確定したわけではない。
- セッション変更時は約0.85秒待つ。受信が途切れるとBlenderは0.75秒で解放。追跡喪失では押下を解除し、復帰しても自動で掴み直さない。
- プレビューはBlenderの可視3Dビューが必要。ポインターが物体内部なら景色が遮られる。まずポインターのみ移動で物体外に出す。
- HTTPスレッドはbpy/gpuへアクセスせず、メインスレッドで生成した画像だけ返す。要求がなければ描画を休止する。
- POSIXはTIME_WAIT後の再起動のためSO_REUSEADDRを使い、Windowsでは同オプションを無効にする。両OSで同じ意味ではないため、一律Trueへ変更しない。
- USBはインターネット共有のネットワーク経由。ケーブルを挿すだけの独自USB転送ではなく、実機でのUSB動作は未確認。

## 検証とビルド

成功CIでSwiftテスト **14件**、Swift生成→Blender互換 **13パケット**、IPA包装 **5件**、Blender pytest **69件**、Xcode端末向けarm64無署名ビルドを確認。WindowsでもBlenderテストと診断ツールテストを確認済み。

Blender **5.2.2 LTS**でバックグラウンドsmoke、GUIで480×270 GPU画像生成、認証HTTP200・未認証401、停止時解放を確認した。これらはiPhone実機確認の代わりではない。

通常のPython環境：

```sh
python -m pip install pytest
cd blender
python -X utf8 -m pytest -q
```

リポジトリルートから包装ツールの検証：

```sh
python -m unittest discover -s tools/tests -p test_package_ipa.py -v
python tools/build_blender_zip.py
```

単独UDP診断の統合テストはWindows向け。macOSのIPA包装工程で `tools/tests` 全体を無差別に実行しない。

macOS + Xcodeで：

```sh
swift test --package-path iOS/SpatialPointerCore
swift run --package-path iOS/SpatialPointerCore PacketFixture > /tmp/spatial-pointer-fixtures.json
python3 tools/check_wire.py /tmp/spatial-pointer-fixtures.json
bash tools/build_unsigned.sh
```

WindowsにはSwift/Xcodeなし。iOSビルドにはGitHub Actionsを使う。Swiftファイルを追加・削除したら `tools/generate_xcode_project.py` の生成方法も確認し、Xcodeプロジェクトへの登録漏れを防ぐ。

無署名IPAはビルド時に署名していないという意味。通常のiPhoneにはユーザーのサイドロード方法で署名して入れる。配布ファイルをソースZIPやシミュレーター用バイナリで代用しない。

## このPCの記録（環境依存・再確認すること）

- 作業リポジトリ：`C:\Programer___Amano\空間マウススマホ\Mouse3DPhone`。その親フォルダーはGit管理外。
- ローカル配布物：`dist/v0.3.0/SpatialPointer-unsigned.ipa`、`spatial_pointer-0.2.0.zip`、各チェックサム。distはGit管理外なので別PCにはcloneされない。
- ローカルIPAは0.3.0 build3、191821 bytes。ダウンロード済み成果物ZIP SHA-256：`6f4aa609a624edfe67c3ac496e9e57337f53700db793799620cec70215673c14`。
- Blender：`C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe`。
- 導入先：`C:\Users\raito\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\spatial_pointer`。実行パッケージ名 `bl_ext.user_default.spatial_pointer`。
- PC側拡張は0.2.0へ更新済み。接続トークンとポインター位置を維持し、UDP受信とPhone pointer viewを再開した。**現在も起動中かは再確認すること。** 導入後にCI向けPOSIXソケット修正が入ったが、Windowsの動作条件は同じ。配布ZIPは最終修正を含む。
- 更新前拡張のバックアップ：`dist/v0.3.0/spatial_pointer-previous-backup.zip`。
- 過去のWi-Fi IPv4：PC `192.168.1.191`、iPhone `192.168.1.174`。DHCPで変わるため固定値扱いしない。Wi-Fi名はKyodoBase。
- 手動Git worktree：隣の `Mouse3DPhone-controls-preview`、ブランチ `codex/pointer-controls-preview`。機能コミットee5cf09時点でmainより古い。今後の作業は最新mainを基準にする。
- 同梱Python：`C:\Users\raito\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。pytestはリポジトリ内 `.test-deps` にあり、必要ならPYTHONPATHに指定。別環境では通常のvenvでよい。

単独診断は `Start-UDP-Test.cmd` で起動し、PCの `http://127.0.0.1:8766/` に表示。Blenderと同時にUDP5005を占有できない。診断の `udp-test-1234` はテスト用の値で、本番のPairing Tokenではない。Blenderへ戻る際は入力を戻す。診断は一時ファイアウォール許可を作り、終了または30分で削除する。IP表示は起動時の値なので経路変更後は再起動する。

## 次のAIが最初に行うこと

1. ユーザーが新しいIPAを入れたか、操作の不満や実機結果が来ているかを確認。すでに実施した操作を何度も要求しない。
2. `git status` と実環境を確認してから編集。トークンを質問・表示せず、Blenderと一致しているかだけ確認する。
3. 新機能の実機確認は `docs/VERIFICATION_IOS.md` の0.3.0チェック項目を使い、必要な項目へ絞る。
4. 実機不具合がなければ、追加のリファクタリングや再ビルドは不要。ユーザーの次の依頼へ進む。

詳細設計：`docs/superpowers/specs/2026-10-20-controls-preview.md`。実装計画：`docs/superpowers/plans/2026-10-20-controls-preview.md`。
