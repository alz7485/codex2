# Catalog Studio — Python デスクトップ版

E3D 4.0 の Catalogue 編集ツールに向けた、操作できるモックアップです。Python 標準の Tkinter を使用します。

## ダウンロード・起動

[Python 版 ZIP をダウンロード](https://github.com/alz7485/codex2/raw/refs/heads/main/catalog-studio-python.zip)し、展開してください。

Python 3.10 以降で、展開先から起動します。外部 Python パッケージのインストールは不要です。

```sh
python main.py
```

Windows では Python をインストールして `start.bat` をダブルクリックするか、`py main.py` を実行してください。公式 Python のインストーラーでは Tcl/Tk を含めてください。

macOS は Tcl/Tk を含む Python を使用してください。Linux ではディストリビューションに合った Tkinter パッケージ（Debian/Ubuntu のシステム Python なら `python3-tk`）とデスクトップ環境が必要です。Linux の起動コマンドは通常 `python3 main.py` です。

Tkinter が使えるかは `python -m tkinter` で確認できます。

![Python 版の画面](python-preview.png)

## 操作できること

- 円筒・円錐台・箱・接続ポイントの追加、複製、削除
- 属性への固定値、パラメータの役割名／番号、四則演算・括弧の入力
- パラメータの追加・削除、役割とサンプル値の編集（一覧でダブルクリックも可）
- 役割名を変更すると、既存の式の参照も更新
- 寸法・方向に連動する概略プレビュー、ドラッグで視点変更
- JSON ファイルの保存・読み込み（既存ブラウザ版のプロジェクト形式と共通）
- 式・名前・正の寸法の基本チェック
- 構成確認用のコメントファイル出力
- 未保存の変更を閉じる・読み込み・新規作成時に確認

左で要素を選び、中央の設定行を選択して式や方向を編集します。サンプル寸法は Enter またはフォーカス移動で反映します。保存は Ctrl+S、読み込みは Ctrl+O、新規作成は Ctrl+N です。デスクトップ版は自動保存せず、JSON に明示的に保存します。

## 現在の範囲

要素、属性、パラメータ番号、役割、寸法は仮仕様です。実機の作成例を確認してから、E3D 出力の解析、PMSET、正しい属性・式の変換、実行用登録マクロを実装します。

プレビューは概略図です。形状の位置は仮に中心、ポイントの位置は仮にグローバル Z 軸の座標として扱います。方向と原点の正式な Catalogue 規則、正確な CAD 表示、接続整合性の検証は未対応です。表示寸法は概略図の範囲に制限されます。プレビューは先頭 12 形状、横の寸法欄は先頭 5 パラメータまで表示し、全パラメータは下の一覧で編集できます。

出力する `.mac` は `$*` コメントだけで、E3D に部品を登録する実行マクロではありません。

## 検証

```sh
python -m unittest discover -s tests -v
```

計算式、禁止構文、参照更新、要素複製、JSON の読み込み・保存をテストします。GUI テストはデスクトップ表示が使える場合のみ実行し、表示がない場合はスキップします。開発環境では仮想ディスプレイ上でも起動・操作を確認しています。Windows/macOS の実機確認は未実施です。

## ファイル構成

- `main.py`：起動用
- `catalog_studio/app.py`：Tkinter 画面
- `catalog_studio/model.py`：プロジェクト、式解析、ファイル処理
- `tests/`：基本テスト
- `index.html`：以前のブラウザ版モックアップ

[ブラウザ版 ZIP](https://github.com/alz7485/codex2/raw/refs/heads/main/catalog-studio-mockup.zip)も残しています。
