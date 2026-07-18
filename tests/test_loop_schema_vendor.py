"""Regression tests for the vendored loop-schema integrity gate."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "template" / "scripts" / "validate_loop_schema_vendor.py"
VENDOR = ROOT / "template" / "scripts" / "_vendor_loop_schemas"


class LoopSchemaVendorIntegrityTests(unittest.TestCase):
    """The generated template must ship a verified, tamper-evident bundle."""

    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        """Run the validator against one synthetic generated-project root."""
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(root)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_template_bundle_is_valid(self) -> None:
        """The canonical template bundle matches its local manifest."""
        result = self.run_validator(ROOT / "template")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_tampering_is_detected(self) -> None:
        """Changing a vendored source file must fail the gate."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            target = project / "scripts" / "_vendor_loop_schemas"
            target.parent.mkdir(parents=True)
            shutil.copytree(VENDOR, target)
            with (target / "models.py").open("a", encoding="utf-8") as handle:
                handle.write("\n# unauthorized local edit\n")

            result = self.run_validator(project)
            self.assertEqual(result.returncode, 1)
            self.assertIn("sha256 mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
