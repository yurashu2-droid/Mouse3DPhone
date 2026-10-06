"""Package an already-built unsigned arm64 iOS app. Never builds or signs it."""
import argparse
import hashlib
import plistlib
import struct
import sys
import zipfile
from pathlib import Path


def package(app: Path, output: Path) -> None:
    app = app.resolve()
    if not app.is_dir() or app.suffix != '.app':
        raise ValueError('A built .app directory is required')
    if (app / '_CodeSignature').exists() or (app / 'embedded.mobileprovision').exists():
        raise ValueError('Bundle contains a code signature or provisioning profile')
    with (app / 'Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    name = info.get('CFBundleExecutable', '')
    if not name or Path(name).name != name:
        raise ValueError('Invalid CFBundleExecutable')
    executable = app / name
    data = executable.read_bytes()
    if len(data) < 32 or struct.unpack_from('<I', data)[0] != 0xFEEDFACF:
        raise ValueError('Expected a thin 64-bit Mach-O executable')
    if struct.unpack_from('<I', data, 4)[0] != 0x0100000C:
        raise ValueError('Expected an iPhone arm64 executable, not a simulator app')
    if struct.unpack_from('<I', data, 12)[0] != 2:
        raise ValueError('Expected a Mach-O application executable')
    commands, command_bytes = struct.unpack_from('<II', data, 16)
    if commands == 0 or 32 + command_bytes > len(data):
        raise ValueError('Invalid Mach-O load commands')
    offset = 32
    ios_device = False
    for _ in range(commands):
        if offset + 8 > 32 + command_bytes:
            raise ValueError('Truncated Mach-O load commands')
        command, size = struct.unpack_from('<II', data, offset)
        if command == 0x1D:  # LC_CODE_SIGNATURE
            raise ValueError('Executable contains a code signature')
        if size < 8 or offset + size > 32 + command_bytes:
            raise ValueError('Invalid Mach-O load command size')
        if command == 0x32 and size >= 24:  # LC_BUILD_VERSION
            ios_device = struct.unpack_from('<I', data, offset + 8)[0] == 2
        offset += size
    if not ios_device:
        raise ValueError('Expected an iOS device build, not an arm64 simulator or macOS app')
    if info.get('CFBundlePackageType') != 'APPL':
        raise ValueError('Expected an APPL bundle')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app.rglob('*')):
            if path.is_symlink():
                raise ValueError('Unexpected symlink in app bundle')
            if not path.is_file():
                continue
            entry = zipfile.ZipInfo('Payload/' + app.name + '/' + path.relative_to(app).as_posix())
            entry.create_system = 3
            mode = 0o755 if path == executable or path.stat().st_mode & 0o111 else 0o644
            entry.external_attr = (0o100000 | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    print(f'Unsigned IPA: {output}')
    print(f'SHA-256: {digest}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        package(args.app, args.output)
    except (ValueError, OSError, plistlib.InvalidFileException) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
