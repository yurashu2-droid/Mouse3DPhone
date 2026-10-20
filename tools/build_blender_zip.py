"""Package the extension sources with the manifest at the ZIP root."""
import argparse
import hashlib
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output_directory: Path) -> Path:
    source = ROOT / 'blender' / 'spatial_pointer'
    manifest = tomllib.loads((source / 'blender_manifest.toml').read_text(encoding='utf-8'))
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"spatial_pointer-{manifest['version']}.zip"
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob('*')):
            relative = file.relative_to(source)
            if (not file.is_file() or file.suffix == '.pyc'
                    or any(part.startswith('.') or part == '__pycache__' for part in relative.parts)):
                continue
            entry = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, file.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or 'blender_manifest.toml' not in archive.namelist():
            raise ValueError('Invalid extension archive')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(f'{output} ({output.stat().st_size} bytes, version {manifest["version"]})')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output_directory)
