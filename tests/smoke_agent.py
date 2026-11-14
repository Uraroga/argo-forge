#!/usr/bin/env python3
"""Opt-in real inference check; never part of unittest discovery."""
from pathlib import Path
import subprocess
import sys
import tempfile

launcher = Path(__file__).resolve().parents[1] / 'localcode.py'
with tempfile.TemporaryDirectory(prefix='argo-agent-', dir=launcher.parent) as folder:
    root = Path(folder)
    source = root / 'calc.py'
    source.write_text('def add(a, b):\n    return a - b\n')
    (root / 'test_calc.py').write_text('import unittest\nfrom calc import add\nclass AddTest(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertEqual(add(-2, 2), 0)\n')
    before = source.read_text()
    test_before = (root / "test_calc.py").read_text()
    baseline = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=root)
    assert baseline.returncode != 0, 'Fixture must fail before agent edit'
    result = subprocess.run([sys.executable, str(launcher), 'code', '--steps', '6', '--output', '512', '--auto-approve', '--prompt',
        'Use shell to inspect calc.py and test_calc.py. Fix add in calc.py. Run python3 -m unittest -v after editing. Report PASS only if tests pass.'], cwd=root, timeout=900)
    assert result.returncode == 0, 'OpenCode failed'
    assert source.read_text() != before, 'No actual file edit'
    assert (root / 'test_calc.py').read_text() == test_before, 'Agent changed acceptance tests'
    subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=root, check=True)
    print('External verification PASS; also inspect OpenCode output for real shell and post-edit test calls.')
