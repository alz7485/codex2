from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
NAME = "FunnelCursorSwitcher"


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
    shutil.copy2(ROOT / "README.md", bundle / "README.md")
    archive = shutil.make_archive(
        str(dist / f"{NAME}-windows-x64"), "zip", root_dir=dist, base_dir=NAME
    )
    print(archive)


if __name__ == "__main__":
    main()
