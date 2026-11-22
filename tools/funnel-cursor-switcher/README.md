# ファンネル・カーソル切替

Windows 10・11 向けの通常ポインター切替ツールです。ファンネルやビットなどを25種類収録しています。Windowsの標準表示（100%）では、縦横比を保った絵を最大32×32ピクセルで表示します。拡大表示向けの画像も収録しています。装備の配色は原作や立体資料を参考にし、色が分からない装備には機体の配色を使っています。

## 使い方

1. [Releases](https://github.com/alz7485/codex2/releases) の「ファンネル・カーソル切替」から `FunnelCursorSwitcher-windows-x64.zip` をダウンロードし、ZIP全体を展開します。
2. `FunnelCursorSwitcher.exe` を起動します。
3. たとえば「ファンネル」→「フィンファンネル」を選び、「適用」を押します。

変更前に戻すには、「元に戻す」→「変更前のカーソル」を選んで「適用」を押します。最初に変更するときに、現在の通常ポインター設定を保存します。待機中や文字入力用などのポインターはWindows側で管理します。

## 移動エフェクト

カーソルを選んで「適用」を押すと、移動中に後端が光り、軌跡が短く残ります。色と噴射の形は収録機体ごとに設定しています。「噴射光と軌跡」のチェックを外すと停止します。

アプリを最小化してもエフェクトは続きます。アプリを閉じるか「元に戻す」を適用すると、エフェクトが消えます。 [動きの見本](https://github.com/alz7485/codex2/blob/main/tools/funnel-cursor-switcher/effect-preview.gif)

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

Pythonから直接使う場合は、Pillowをインストールしてから起動します。

```powershell
py -3.12 -m pip install Pillow==12.3.0
py -3.12 .\FunnelCursorSwitcher.pyw
```
