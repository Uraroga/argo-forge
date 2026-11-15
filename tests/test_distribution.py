"""Audit di pubblicazione senza Docker, rete, estrazione archivi o staging."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('distribution_audit', ROOT / 'tools/audit_distribution.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DistributionTests(unittest.TestCase):
    def fixture(self, root):
        (root / '.dockerignore').write_text('**\n!Dockerfile\n!.dockerignore\n')
        (root / 'Dockerfile').write_text('FROM base AS build\nFROM base AS runtime\nCOPY --from=build /out/bin /bin\n')

    def test_real_docker_context_contains_only_two_control_files(self):
        self.assertEqual(audit.docker_context_files(ROOT), ['.dockerignore', 'Dockerfile'])

    def test_widened_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            with (root / '.dockerignore').open('a') as out:
                out.write('!backups/**\n')
            with self.assertRaises(audit.AuditError):
                audit.docker_context_files(root)

    def test_dockerfile_specific_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            (root / 'Dockerfile.dockerignore').write_text('')
            with self.assertRaises(audit.AuditError):
                audit.docker_context_files(root)

    def test_local_copy_add_and_external_stage_are_rejected(self):
        for instruction in ('COPY . /app', 'ADD backup.tgz /app', 'COPY --from=unknown /out /app'):
            with self.subTest(instruction=instruction), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.fixture(root)
                with (root / 'Dockerfile').open('a') as out:
                    out.write(instruction + '\n')
                with self.assertRaises(audit.AuditError):
                    audit.docker_context_files(root)

    def test_context_does_not_open_excluded_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            private = root / 'backups'
            private.mkdir()
            (private / 'private.tgz').write_bytes(b'not an archive to extract')
            names = {'.dockerignore', 'Dockerfile', 'distribution-files.txt'}
            (root / 'distribution-files.txt').write_text('\n'.join(sorted(names)))
            original = Path.read_bytes
            def guarded(path):
                self.assertNotIn('backups', path.parts)
                return original(path)
            with patch.object(audit, 'git_files', return_value=names), patch.object(audit, 'git_ignored_files', return_value=set()), patch.object(Path, 'read_bytes', new=guarded):
                self.assertEqual(audit.audit(root)['archives_opened'], 0)

    def test_forced_tracked_ignored_file_is_rejected_even_if_declared(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            names = {'backups/private.tgz'}
            (root / 'distribution-files.txt').write_text('backups/private.tgz\n')
            with patch.object(audit, 'git_files', return_value=names), patch.object(audit, 'git_ignored_files', return_value=names), patch.object(Path, 'read_bytes', side_effect=AssertionError('Archivio aperto')):
                with self.assertRaises(audit.AuditError):
                    audit.audit(root)

    def test_unexpected_git_candidate_fails_before_reading_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'distribution-files.txt').write_text('README.md\n')
            with patch.object(audit, 'git_files', return_value={'README.md', 'private-file'}), patch.object(Path, 'read_bytes', side_effect=AssertionError('Contenuti inattesi letti')):
                with self.assertRaises(audit.AuditError):
                    audit.audit(root)

    def test_manifest_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('../secret', '/etc/passwd'):
                with self.assertRaises(audit.AuditError):
                    audit.regular_file(root, name)
            (root / 'link').symlink_to('/does/not/exist')
            with self.assertRaises(audit.AuditError):
                audit.regular_file(root, 'link')

    def test_env_example_only_allows_dummy_values(self):
        audit.check_example('# Solo segnaposto\nAPI_KEY=REPLACE_ME\nOPTION=\n')
        with self.assertRaises(audit.AuditError):
            audit.check_example('API_KEY=not-a-placeholder')

    def test_secret_detection_does_not_return_values(self):
        fake = ('ghp_' + 'x' * 36).encode()
        result = audit.secret_types(fake)
        self.assertEqual(result, ['token GitHub'])
        self.assertNotIn(fake.decode(), str(result))

    def test_git_excludes_private_runtime_material(self):
        excluded = ['.env', '.env.local', '.env-production', 'nested/.env',
                    '.dashboard-access.txt', 'backups/private.tgz', 'nested/backups/private.zip',
                    'evidence/session.json', 'docs/reports/codex/local.md', 'token.json',
                    'private.token', 'private.key', 'password.txt', 'sessions/message.json',
                    'conversations/message.json', 'transcripts/voice.txt', 'memories/user.md',
                    'state.sqlite3', 'state.sqlite3-wal', 'local.db-shm', 'models/model.gguf',
                    'model.gguf', 'voice.onnx', 'weights.bin', 'model.safetensors',
                    'opencode-local/bin/opencode', 'opencode-local/node_modules/package/index.js',
                    '.cache/data', '.venv/bin/python', 'temp.tmp', 'old.bak', 'logs/local.log']
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin', '-z'], cwd=ROOT,
                                input=('\0'.join(excluded) + '\0').encode(), capture_output=True, check=True)
        self.assertEqual(set(filter(None, result.stdout.decode().split('\0'))), set(excluded))

    def test_git_keeps_public_sources_and_fake_example(self):
        names = ['.env.example', 'localcode.py', 'Dockerfile', 'opencode-local/tools/shell.ts',
                 'docs/TIMEOUTS.md', 'tests/test_localcode.py', 'distribution-files.txt']
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin', '-z'], cwd=ROOT,
                                input=('\0'.join(names) + '\0').encode(), capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'')

    def test_smoke_deadline_is_not_changed_to_six_hours(self):
        tree = ast.parse((ROOT / 'tests/smoke_agent.py').read_text())
        timeouts = [k.value.value for call in ast.walk(tree) if isinstance(call, ast.Call)
                    for k in call.keywords if k.arg == 'timeout' and isinstance(k.value, ast.Constant)]
        self.assertEqual(timeouts, [900])
