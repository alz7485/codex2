"""Package only application source and explicitly selected synthetic examples."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
ROOT_FILES = ('.gitattributes','README.md','BUILD_ONEDIR.md','main.py','start.bat','install.bat',
              'build_onedir.bat','requirements.txt','requirements-build.txt','package_python.py')
DOC_FILES = ('sdte-cmpt-create.png','cate-bundle.png','text-preset-batch.png','preview-defaults.png','catalog-folders.png','spec-folders.png','ptset-preview.png','valve-sample.png','macro-buttons.png','catalog-workspace.png','spec-combination.png','macro-import.png','manual-updates.png','ptset-create.png','ptset-add.png','attribute-edit.png','ptset-preset-confirm.png','ptset-canvas.png','ptset-shared-dimensions.png','ptset-canvas-menu.png','gmset-create.png','gmset-scom.png','gmset-shared-dimensions.png','gmset-wireframe.png','gmset-transparent.png','outline-create.png','parameter-presets.png','parameter-preset-create.png','element-presets.png')
EXAMPLE_FILES = ('valve-sample.json','catalog-workspace-sample.json','integrated-sample.json','construction-sample.json','catalog-book.pdf','creation-import-sample.mac','creation-export-sample.mac','alp-creation-sample.mac',
                 'catalogue-rules-sample.json','catalogue-rules-book.pdf','parameter-presets-sample.json','parameter-presets-book.pdf','element-presets-sample.json','gmset-3d-sample.json','gmset-display-sample.json','parameter-text-sample.json','ptset-shared-dimensions.json','gmset-shared-dimensions.json','manual-compatibility-sample.json')
ASSET_FILES = ('catalog-studio.png', 'catalog-studio.ico')


def build():
    files = [ROOT/name for name in ROOT_FILES]
    files += sorted((ROOT/'catalog_studio').glob('*.py'))
    files += sorted((ROOT/'tests').glob('*.py'))
    files += [ROOT/'docs'/name for name in DOC_FILES]
    files += [ROOT/'examples'/name for name in EXAMPLE_FILES]
    files += [ROOT/'assets'/name for name in ASSET_FILES]
    path=ROOT/'catalog-studio-integrated.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            if not file.is_file() or file.is_symlink(): raise ValueError('Unexpected package file: '+str(file))
            archive.write(file,file.relative_to(ROOT))
    for name in ('catalog-studio-python.zip','catalog-studio-ui.zip'):shutil.copyfile(path,ROOT/name)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():raise ValueError('Archive integrity check failed.')
    print(f'{path.name}: {len(files)} files, {path.stat().st_size} bytes')
    return path


if __name__ == '__main__':build()
