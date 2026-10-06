#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproducible, dependency-free ZIP builder. Does not upload or install anything."""
from __future__ import annotations
import argparse
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAMP = (2026, 10, 6, 0, 0, 0)


def _put(zf: zipfile.ZipFile, source: Path, name: str):
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, source.read_bytes())


def build_extension(output_dir: Path) -> Path:
    source = ROOT / 'spatial_pointer'
    manifest = tomllib.loads((source/'blender_manifest.toml').read_text())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir/f"spatial_pointer-{manifest['version']}.zip"
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(source.rglob('*')):
            if not file.is_file() or file.is_symlink():
                continue
            rel = file.relative_to(source)
            if '__pycache__' in rel.parts or file.suffix not in {'.py', '.toml', '.md'} and file.name != 'LICENSE':
                continue
            _put(zf, file, rel.as_posix())
    return output


def build_kit(output_dir: Path, extension: Path) -> Path:
    output = Path(output_dir)/'Spatial_Pointer_v0.1.1_Development_Kit.zip'
    skip = {'.git', '.pytest_cache', '__pycache__', '.superpowers'}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(ROOT.rglob('*')):
            rel = file.relative_to(ROOT)
            if not file.is_file() or file.is_symlink() or any(p in skip for p in rel.parts):
                continue
            if file.suffix in {'.pyc', '.zip'} or file.name.startswith(('red_', 'green_')):
                continue
            _put(zf, file, 'Spatial_Pointer_Kit/'+rel.as_posix())
        _put(zf, extension, 'Spatial_Pointer_Kit/Install/'+extension.name)
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT.parent)
    args = p.parse_args()
    extension = build_extension(args.output)
    print(extension)
    print(build_kit(args.output, extension))
