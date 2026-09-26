"""Win7 packaging payload regression using real PyInstaller 4.10 archives.

Run with the separate build toolchain; normal development does not install it.
Valid embedded bytecode must pass without unpacked Python sources. Missing or
corrupt modules, decoy source directories and neighboring EXEs must fail.
"""
from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

import validate_dist_exe as validator


class TestNetworkxFrozenPayload(unittest.TestCase):
    def setUp(self):
        try:
            pyinstaller = importlib.import_module("PyInstaller")
        except ImportError:
            self.skipTest("Requires the separate Win7 build toolchain (PyInstaller 4.10)")
        if pyinstaller.__version__ != "4.10":
            self.skipTest("Win7 packaging is locked to PyInstaller 4.10")
        writers = importlib.import_module("PyInstaller.archive.writers")
        readers = importlib.import_module("PyInstaller.loader.pyimod02_archive")
        self.carchive_writer = writers.CArchiveWriter
        self.pyz_writer = writers.ZlibArchiveWriter
        self.pyz_reader = readers.ZlibArchiveReader
        self.temp = tempfile.TemporaryDirectory(prefix="aps-networkx-payload-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, missing=(), invalid_code=None, invalid_kind=None, corrupt=None, basename="aps"):
        modules = [name for name in validator._NETWORKX_MODULE_ANCHORS if name not in missing]
        codes, toc = {}, []
        for name in modules:
            path = name.replace(".", "/") + ("/__init__.py" if name == "networkx" else ".py")
            if name == invalid_kind:
                path = "not_a_package.py"
            codes[name] = "not a code object" if name == invalid_code else compile("pass", path, "exec")
            toc.append((name, path, "PYMODULE"))
        pyz = self.root / (basename + ".pyz")
        self.pyz_writer(str(pyz), toc, code_dict=codes)
        if corrupt:
            reader = self.pyz_reader(str(pyz))
            _kind, offset, length = reader.toc[corrupt]
            blob = bytearray(pyz.read_bytes())
            blob[offset:offset + length] = b"!" * length
            pyz.write_bytes(blob)
        exe = self.root / (basename + ".exe")
        self.carchive_writer(str(exe), [("PYZ-00.pyz", str(pyz), 0, "z")], pylib_name="python38.dll")
        exe.write_bytes(b"MZ-test-container-prefix" + exe.read_bytes())
        return exe

    def test_valid_pyz_needs_no_source_directory(self):
        exe = self.archive()
        self.assertFalse((self.root / "networkx").exists())
        validator._assert_networkx_bundled(str(exe))

    def test_every_required_module_is_enforced(self):
        for index, module in enumerate(validator._NETWORKX_MODULE_ANCHORS):
            with self.subTest(module=module):
                exe = self.archive(missing=(module,), basename="missing-" + str(index))
                with self.assertRaisesRegex(RuntimeError, module):
                    validator._assert_networkx_bundled(str(exe))

    def test_corrupted_bytecode_is_rejected(self):
        exe = self.archive(corrupt="networkx.algorithms.dag")
        with self.assertRaises(RuntimeError):
            validator._assert_networkx_bundled(str(exe))

    def test_marshaled_data_cannot_masquerade_as_module_code(self):
        exe = self.archive(invalid_code="networkx.algorithms.bipartite.matching")
        with self.assertRaisesRegex(RuntimeError, "networkx.algorithms.bipartite.matching"):
            validator._assert_networkx_bundled(str(exe))

    def test_networkx_root_must_be_a_package(self):
        exe = self.archive(invalid_kind="networkx")
        with self.assertRaisesRegex(RuntimeError, "networkx"):
            validator._assert_networkx_bundled(str(exe))

    def test_source_decoy_and_neighboring_valid_exe_do_not_hide_missing_module(self):
        self.archive(basename="good_neighbor")
        exe = self.archive(missing=("networkx",), basename="target")
        (self.root / "networkx").mkdir()
        (self.root / "networkx/__init__.py").write_text('__version__ = "3.1"', encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "networkx"):
            validator._assert_networkx_bundled(str(exe))

    def test_plain_file_and_truncated_archive_are_rejected(self):
        plain = self.root / "plain.exe"
        plain.write_bytes(b"networkx networkx.algorithms.dag")
        with self.assertRaises(RuntimeError):
            validator._assert_networkx_bundled(str(plain))
        exe = self.archive()
        exe.write_bytes(exe.read_bytes()[:-88])
        with self.assertRaises(RuntimeError):
            validator._assert_networkx_bundled(str(exe))



if __name__ == "__main__":
    unittest.main(verbosity=2)
