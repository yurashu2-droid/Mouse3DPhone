"""Package the dependency-free PC prototype, keeping the launcher directory layout."""
from pathlib import Path
import argparse
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(output, engine=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / 'Start-Bullet-Pet.cmd', ROOT / 'Start-Bullet-Pet-3D.cmd']
    paths += [p for p in (ROOT / 'games' / 'bullet_pet').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and '.godot' not in p.parts
              and p.suffix in {'.py', '.ps1', '.js', '.html', '.css', '.md', '.gd', '.tscn', '.godot', '.gdshader', '.uid'}]
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            archive.write(path, path.relative_to(ROOT).as_posix())
        if engine:
            archive.write(engine, 'runtime/Godot.exe')
            for name in ('LICENSE.txt', 'COPYRIGHT.txt'):
                archive.write(engine.parent / name, 'runtime/'+name)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert 'games/bullet_pet/web/phone.html' in archive.namelist()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(f'{output}: {len(paths)} files, {output.stat().st_size} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot-exe', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'dist'/'BulletPet-PC.zip')
    args = parser.parse_args()
    package(args.output, args.godot_exe)
