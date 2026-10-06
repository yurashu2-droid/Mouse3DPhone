# 検証記録 — Spatial Pointer v0.1

## 実施したこと

作成環境：Linux x86_64、Python 3.13.5。Blenderはこの環境にインストールされていません。

- 60項目のpytestテスト：データの型・NaN・サイズ・トークン検証、座標系変換、四元数、相対追従、クラッチ、追従復帰、倍率変更、平滑化、シーケンス順序、送信元固定を確認。
- 実際のUDPソケットを使用したループバック送受信、受信数制限、ポート解放、不正パケットの除外。
- 別プロセスの`tools/udp_sender.py`から`UDPReceiver`への送信と、終了時の解放・追従停止パケット。
- Blender用モジュールを含むPython構文コンパイル。
- マニフェスト必須値とインストールZIP内のファイル配置、破損、不要なキャッシュの混入を検査。

**これらはBlender本体を起動した統合テストではありません。** 60件の中には、Blender向けソースの構文・静的な契約確認が3件含まれます。ログはverification/final_tests.logです。

## 未実施

- Blender本体での拡張インストール・有効化・Nパネル描画。
- 実際のBlenderビューポートでのキーイベント・掴み操作・ヘルパー表示・ライフサイクル。
- Blender公式CLIによるextension validate。
- iPhone実機の6DoF計測、送信、遅延、ジッター、キャリブレーション。
- Windows/macOS上でのBlender実行。

マニフェストはBlender 4.2以降を対象にしていますが、この下限指定は全バージョンの実機検証を意味しません。

## Blender本体で実行する自己テスト

開発キットを解凍したフォルダで、`blender`がコマンドとして利用できる場合：

```console
blender --background --factory-startup --python tests/blender_smoke.py
```

Windowsなどで`blender`がPATHにない場合は、その部分をインストール済みBlenderの実行ファイルのパスに置き換えます。例示のバージョン番号からインストール先を決めつけないでください。

この自己テストは新しいバックグラウンドのBlenderで実行する前提です。ユーザーが作業中のBlenderには接続せず、ファイルの保存・上書きもしません。拡張の登録、ヘルパー作成、掴んで移動・回転、取消・復元、練習シーンの非破壊作成、登録解除を確認し、成功時に`SPATIAL_POINTER_BLENDER_SMOKE: PASS`と表示します。

拡張の公式パッケージ検証：

```console
blender --command extension validate Install/spatial_pointer-0.1.1.zip
```

テストコードは同梱していますが、この作成環境ではこれらのBlenderコマンドを実行できていません。

## ローカル開発テスト

```console
python -m pip install pytest
python -m pytest -q
python -m compileall -q spatial_pointer tools tests
python tools/build_release.py --output dist
```

pytestは開発用です。アドオン使用に追加のPythonライブラリは不要です。
