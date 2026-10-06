import hashlib
import importlib.util
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'package_ipa.py'


class PackageTests(unittest.TestCase):
    def make_app(self, root, cpu=0x0100000C, platform=2):
        app = root / 'SpatialPointer.app'
        app.mkdir()
        (app / 'Info.plist').write_bytes(plistlib.dumps({
            'CFBundleExecutable': 'SpatialPointer',
            'CFBundleIdentifier': 'dev.yurashu2.spatialpointer',
            'CFBundlePackageType': 'APPL',
            'MinimumOSVersion': '16.0',
        }))
        # A thin Mach-O header and LC_BUILD_VERSION, enough to check packaging.
        (app / 'SpatialPointer').write_bytes(struct.pack('<8I', 0xFEEDFACF, cpu, 0, 2, 1, 24, 0, 0)
                                             + struct.pack('<6I', 0x32, 24, platform, 0x100000, 0x120000, 0))
        return app

    def run_packager(self, app, output):
        return subprocess.run([sys.executable, str(SCRIPT), '--app', str(app), '--output', str(output)],
                              text=True, capture_output=True)

    def test_real_bundle_layout_digest_and_executable_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root)
            output = root / 'dist' / 'SpatialPointer-unsigned.ipa'
            result = self.run_packager(app, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                self.assertIn('Payload/SpatialPointer.app/Info.plist', archive.namelist())
                entry = archive.getinfo('Payload/SpatialPointer.app/SpatialPointer')
                self.assertTrue((entry.external_attr >> 16) & 0o111)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            self.assertEqual(output.with_suffix('.ipa.sha256').read_text().split()[0], digest)

    def test_rejects_simulator_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.run_packager(self.make_app(root, 0x01000007), root / 'bad.ipa')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('arm64', result.stderr)

    def test_rejects_source_renamed_as_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root)
            (app / 'SpatialPointer').write_text('import SwiftUI')
            result = self.run_packager(app, root / 'bad.ipa')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Mach-O', result.stderr)

    def test_rejects_arm64_simulator_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.run_packager(self.make_app(root, platform=7), root / 'bad.ipa')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('iOS device', result.stderr)

    def test_rejects_signed_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root)
            (app / '_CodeSignature').mkdir()
            result = self.run_packager(app, root / 'bad.ipa')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('signature', result.stderr)


if __name__ == '__main__':
    unittest.main()
