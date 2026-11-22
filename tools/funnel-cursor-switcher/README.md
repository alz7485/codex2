# ファンネル・カーソル切替

Windows 10・11 向けの通常ポインター切替ツールです。20×20ピクセルのファンネルやビットなどを16種類収録しています。

## 使い方

1. [Releases](https://github.com/alz7485/codex2/releases) の「ファンネル・カーソル切替」から `FunnelCursorSwitcher-windows-x64.zip` をダウンロードし、ZIP全体を展開します。
2. `FunnelCursorSwitcher.exe` を起動します。
3. たとえば「ファンネル」→「フィンファンネル」を選び、「適用」を押します。

変更前に戻すには、「元に戻す」→「変更前のカーソル」を選んで「適用」を押します。最初に変更するときに、現在の通常ポインター設定を保存します。待機中や文字入力用などのポインターはWindows側で管理します。

## カーソルの追加

EXEと同じ場所の `カーソル` フォルダに分類フォルダを作り、中に `.cur` または `.ani` を入れてアプリを再起動します。同名の `.png` があればプレビューに表示します。

```text
FunnelCursorSwitcher/
├── FunnelCursorSwitcher.exe
├── _internal/
└── カーソル/
    ├── ファンネル/
    │   ├── フィンファンネル.cur
    │   └── フィンファンネル.png
    └── 自作/
        └── 好きなカーソル.cur
```

`_internal` と `カーソル` を含むフォルダごと使います。

## Windowsでビルド

64ビット版 Python 3.12 をPATHに追加した環境で、このフォルダから次を実行します。

```powershell
.\build-onedir.cmd
```

出力先は `dist\FunnelCursorSwitcher-windows-x64.zip` です。バッチは仮想環境を作り、PyInstallerで次のコマンドを実行してから、カーソルフォルダをコピーしてZIPにします。

```powershell
.\.venv-build\Scripts\python.exe -m PyInstaller --onedir --windowed --clean --noconfirm --name FunnelCursorSwitcher FunnelCursorSwitcher.pyw
```

Pythonから直接使う場合は `py -3.12 .\FunnelCursorSwitcher.pyw` で起動できます。追加パッケージはビルド時に使用します。
