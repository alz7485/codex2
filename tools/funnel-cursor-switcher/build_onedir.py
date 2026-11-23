from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
NAME = "FunnelCursorSwitcher"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def main():
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("Build with 64-bit Python on Windows.")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--onedir", "--windowed",
            "--clean", "--noconfirm", "--name", NAME, f"{NAME}.pyw",
        ],
        cwd=ROOT,
        check=True,
    )

    dist = ROOT / "dist"
    bundle = dist / NAME
    shutil.copytree(ROOT / "カーソル", bundle / "カーソル", dirs_exist_ok=True)
    shutil.copytree(ROOT / "飛行アニメ", bundle / "飛行アニメ", dirs_exist_ok=True)
    for name in ("VERSION", "README.md", "検証記録.md", "特殊アクション仕様.md", "開発対象.md",
                 "active-actions-preview.gif", "equipment-actions-preview.gif",
                 "shield-preview.gif", "shield-assembly.png", "spiral-preview.gif", "dragoon-preview.gif",
                 "barrier-preview.gif", "cannon-preview.gif", "volley-preview.gif"):
        shutil.copy2(ROOT / name, bundle / name)
    archive = shutil.make_archive(
        str(dist / f"{NAME}-v{VERSION}-windows-x64"), "zip", root_dir=dist, base_dir=NAME
    )
    # Keep the existing release workflow and old download name compatible.
    shutil.copy2(archive, dist / f"{NAME}-windows-x64.zip")
    print(archive)


if __name__ == "__main__":
    main()
