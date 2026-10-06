from pathlib import Path
import tomllib
import zipfile
from tools.build_release import build_extension

ROOT = Path(__file__).resolve().parents[1]


def test_extension_metadata_is_self_contained():
    data = tomllib.loads((ROOT/'spatial_pointer'/'blender_manifest.toml').read_text())
    assert data['schema_version'] == '1.0.0'
    assert data['id'] == 'spatial_pointer'
    assert data['type'] == 'add-on'
    assert data['blender_version_min'] == '4.2.0'
    assert data['license'] == ['SPDX:GPL-3.0-or-later']
    assert 0 < len(data['tagline']) <= 64
    assert not data['tagline'].endswith('.')
    assert 'network' in data['permissions']
    assert not data.get('wheels')


def test_install_zip_layout_and_contents(tmp_path):
    path = build_extension(tmp_path)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for required in ('__init__.py', 'blender_manifest.toml', 'addon.py',
                         'runtime.py', 'visuals.py', 'core.py', 'transport.py', 'README_JA.md', 'LICENSE'):
            assert required in names
        assert not any('__pycache__' in n or '.git' in n or n.endswith('.pyc') for n in names)
        assert not any(n.startswith('/') or '..' in Path(n).parts for n in names)
        assert z.testzip() is None
