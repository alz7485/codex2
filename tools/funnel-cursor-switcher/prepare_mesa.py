"""Copy OSMesa and its packaged DLL dependencies, plus their license notices."""
from pathlib import Path
import shutil
import pefile

root = Path(__file__).parent
source = root / "mesa-download"
target = root / "mesa"
target.mkdir(exist_ok=True)
candidates = []
for path in source.rglob("osmesa.dll"):
    with pefile.PE(str(path), fast_load=True) as image:
        if image.FILE_HEADER.Machine == 0x8664:
            candidates.append(path)
if len(candidates) != 1:
    raise RuntimeError(f"Expected one x64 OSMesa driver, found {candidates}")
folder = candidates[0].parent
libraries = {p.name.lower(): p for p in folder.glob("*.dll")}
pending = [candidates[0]]
copied = set()
while pending:
    path = pending.pop()
    if path.name.lower() in copied:
        continue
    copied.add(path.name.lower())
    shutil.copy2(path, target / path.name)
    with pefile.PE(str(path)) as image:
        for descriptor in (*getattr(image, "DIRECTORY_ENTRY_IMPORT", ()),
                           *getattr(image, "DIRECTORY_ENTRY_DELAY_IMPORT", ())):
            dependency = libraries.get(descriptor.dll.decode("ascii").lower())
            if dependency is not None:
                pending.append(dependency)
licenses = target / "licenses"
licenses.mkdir(exist_ok=True)
for path in source.rglob("*"):
    if path.is_file() and any(word in path.name.lower() for word in ("license", "copying", "copyright")):
        destination = licenses / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
print("OSMesa runtime files", sorted(copied))
