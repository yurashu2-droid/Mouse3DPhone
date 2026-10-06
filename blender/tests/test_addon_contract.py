from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_blender_modules_exist_and_compile():
    for name in ['__init__.py', 'addon.py', 'runtime.py', 'visuals.py']:
        path = ROOT / 'spatial_pointer' / name
        assert path.is_file(), f'Missing Blender module: {name}'
        compile(path.read_text(), str(path), 'exec')


def test_bpy_modules_do_not_spawn_background_threads():
    for path in (ROOT / 'spatial_pointer').glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name not in {'threading', 'subprocess'} for a in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {'threading', 'subprocess'}


def test_bpy_property_annotations_are_evaluated():
    path = ROOT / 'spatial_pointer' / 'addon.py'
    assert path.exists()
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            assert 'annotations' not in [a.name for a in node.names]


def test_modal_timer_does_not_access_removed_event_timer_attribute():
    path = ROOT / 'spatial_pointer' / 'addon.py'
    tree = ast.parse(path.read_text())
    removed_accesses = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == 'timer'
        and isinstance(node.value, ast.Name)
        and node.value.id == 'event'
    ]
    assert not removed_accesses, (
        "Blender Event has no 'timer' attribute; handle modal timer events via event.type == 'TIMER'"
    )
