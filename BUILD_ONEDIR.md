# Windows onedir EXE 化

この ZIP は Python ソースとビルド用コマンドを含みます。Windows EXE 自体は同梱していません。

## 手順

1. Windows に Tcl/Tk を含む Python 3.10 以降をインストール。
2. ZIP を展開。
3. `build_onedir.bat` をダブルクリック。
4. 完了後、`dist\CatalogStudio\CatalogStudio.exe` を起動。

ビルド用の `.build-venv` を作成し、Pillow・ReportLab・PyInstaller をインストールします。初回インストールには PyPI への通信が必要です。

**配布するときは `dist\CatalogStudio` フォルダー全体を ZIP にしてください。** `CatalogStudio.exe` 単体では動作しません。`_internal` 内の Tk ライブラリ、Python DLL、ReportLab 等も必要です。

## 手動コマンド（Windows のコマンドプロンプト）

展開先で実行します。

```bat
py -3 -m venv .build-venv
.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name CatalogStudio --collect-all reportlab --add-data "examples;examples" main.py
```

Python Launcher (`py`) がない場合は、最初のコマンドを `python -m venv .build-venv` に置き換えてください。

`--onedir` がフォルダー形式、`--windowed` がコンソール非表示です。PDF 用データを含めるために `--collect-all reportlab`、自作サンプルを同梱するために `--add-data` を指定しています。ビルド出力の `build/` と `dist/CatalogStudio/` は同名の既存出力を更新します。

## 動作確認

ビルド後は以下を確認してください。

- PTSET・GMSET 作成画面が開く。
- 要素追加、属性編集、JSON 保存と再読み込みができる。
- 以前の CATE・SCOM、SPEC、PDF 画面へ移動できる。
- PDF が必要な場合、冊子を作成し PDF を保存できる。
- 配布するフォルダー全体を別の場所にコピーして起動できる。

Windows ビルドは Windows 上で行ってください。今回の開発環境では Python GUI を検証していますが、Windows の EXE ビルド・起動は未実施です。
