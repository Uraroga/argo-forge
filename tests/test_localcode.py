"""Contratto timeout e gestione container, solo mock: nessun Docker o LLM reale."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError

spec = importlib.util.spec_from_file_location('localcode', Path(__file__).parents[1] / 'localcode.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        # Un nuovo percorso non simulato deve fallire, non contattare il sistema reale.
        for name in ('run', 'check_output'):
            guard = patch.object(m.subprocess, name, side_effect=AssertionError('Sottoprocesso non simulato'))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(m, 'urlopen', side_effect=AssertionError('HTTP non simulato'))
        guard.start()
        self.addCleanup(guard.stop)

    def state(self, running=True):
        command = m.server_command()
        return {
            'Config': {'Cmd': command[command.index(m.IMAGE)+1:], 'Labels': {'localcode.managed': 'true'}},
            'State': {'Running': running}, 'Image': 'sha256:fixture',
            'Mounts': [{'Source': str(m.MODEL), 'Destination': '/models/lfm25.gguf', 'RW': False}],
            'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18080'}]}},
        }

    def test_timeout_units(self):
        self.assertIs(type(m.REQUEST_TIMEOUT_SECONDS), int)
        self.assertEqual(m.REQUEST_TIMEOUT_SECONDS, 6 * 60 * 60)
        self.assertIs(type(m.REQUEST_TIMEOUT_MS), int)
        self.assertEqual(m.REQUEST_TIMEOUT_MS, m.REQUEST_TIMEOUT_SECONDS * 1000)
        self.assertGreater(m.REQUEST_TIMEOUT_MS, 0)

    def test_fixed_server_contract(self):
        cmd = m.server_command()
        for flag, value in {'--ctx-size': '131072', '-p': '127.0.0.1:18080:8080',
                            '--n-gpu-layers': '0', '--parallel': '1', '--threads': '2',
                            '--threads-batch': '2', '--timeout': '21600'}.items():
            self.assertEqual(cmd.count(flag), 1)
            self.assertEqual(cmd[cmd.index(flag)+1], value)
        self.assertIn('readonly', cmd[cmd.index('--mount')+1])
        self.assertIn('--jinja', cmd)
        self.assertIn('--metrics', cmd)
        self.assertNotIn('--privileged', cmd)
        self.assertNotIn('rm', cmd)

    def test_tool_permission(self):
        cfg = m.opencode_config('lfm', 24, 256)
        self.assertEqual(cfg['enabled_providers'], ['llama.cpp'])
        for key in ('timeout', 'headerTimeout', 'chunkTimeout'):
            value = cfg['provider']['llama.cpp']['options'][key]
            self.assertIs(type(value), int)  # bool è una sottoclasse int: va escluso.
            self.assertEqual(value, 21600000)
        self.assertEqual(cfg['provider']['llama.cpp']['options']['baseURL'], m.BASE_URL + '/v1')
        self.assertEqual(cfg['agent']['local-build']['permission']['shell'], 'ask')
        self.assertEqual(m.opencode_config('lfm', 8, 256, True)['agent']['local-build']['permission']['shell'], 'allow')

    def test_client_budgets_and_local_tools_preserved(self):
        cfg = m.opencode_config('model-id', 7, 123)
        self.assertEqual(cfg['small_model'], cfg['model'])
        self.assertEqual(cfg['provider']['llama.cpp']['models']['model-id']['limit'], {'context': 131072, 'output': 123})
        self.assertEqual(cfg['agent']['local-build']['steps'], 7)
        self.assertEqual(cfg['agent']['local-build']['tools'], {'*': False, 'shell': True})
        self.assertEqual(cfg['plugin'], [])
        self.assertEqual(cfg['mcp'], {})

    def test_foreign_container_untouched(self):
        with patch.object(m, 'inspect', return_value={'Config': {'Labels': {}}}):
            with self.assertRaises(m.LocalCodeError):
                m.managed()
        m.subprocess.run.assert_not_called()

    def test_transient_health_errors(self):
        errors = [URLError('fixture'), TimeoutError(), ConnectionResetError(), '{', '{"status":"ok"}']
        with patch.object(m, 'docker_inspect', return_value='true'), patch.object(m, 'endpoint', side_effect=errors), patch.object(m.time, 'sleep'):
            m.wait_for_server()

    def test_startup_deadline_remains_short(self):
        with patch.object(m.time, 'monotonic', side_effect=[100, 100, 701]), patch.object(m.time, 'sleep'), patch.object(m, 'docker_inspect', return_value='true'), patch.object(m, 'endpoint', side_effect=TimeoutError()) as endpoint:
            with self.assertRaises(m.LocalCodeError):
                m.wait_for_server()  # default 600 s, nessuna attesa reale.
            endpoint.assert_called_once_with('/health')

    def test_health_http_timeout_is_two_seconds(self):
        with patch.object(m, 'urlopen') as http:
            http.return_value.__enter__.return_value.read.return_value = b'{"status":"ok"}'
            self.assertEqual(m.endpoint('/health'), '{"status":"ok"}')
            http.assert_called_once_with(m.BASE_URL + '/health', timeout=2)

    def test_model_discovery_timeout_is_ten_seconds(self):
        with patch.object(m, 'endpoint', return_value='{"data":[{"id":"actual-model"}]}') as endpoint:
            self.assertEqual(m.actual_model_id(), 'actual-model')
            endpoint.assert_called_once_with('/v1/models', timeout=10)

    def test_invalid_mount_rejected(self):
        for change in ({'RW': True}, {'Source': '/other/model.gguf'}, {'Destination': '/other.gguf'}):
            with self.subTest(change=change):
                state = self.state()
                state['Mounts'][0].update(change)
                with self.assertRaises(m.LocalCodeError):
                    m.validate(state)
        m.subprocess.run.assert_not_called()

    def test_invalid_binding_rejected(self):
        state = self.state()
        state['HostConfig']['PortBindings']['8080/tcp'][0]['HostIp'] = '0.0.0.0'
        with self.assertRaises(m.LocalCodeError):
            m.validate(state)
        m.subprocess.run.assert_not_called()

    def test_image_change_requires_manual_decision(self):
        with patch.object(m.subprocess, 'check_output', return_value='sha256:different'):
            with self.assertRaises(m.LocalCodeError):
                m.validate(self.state())
        m.subprocess.run.assert_not_called()

    def test_compatible_container_validated(self):
        with patch.object(m.subprocess, 'check_output', return_value='sha256:fixture') as read:
            m.validate(self.state())
            read.assert_called_once_with(['docker', 'image', 'inspect', m.IMAGE, '--format', '{{.Id}}'], text=True)
        m.subprocess.run.assert_not_called()

    def test_running_legacy_server_blocks_start(self):
        with patch.object(m.subprocess, 'check_output', return_value='llama-cpp-lfm25\n'), patch.object(m, 'inspect', return_value={'Mounts': []}):
            with self.assertRaises(m.LocalCodeError):
                m.ensure_server()
        m.subprocess.run.assert_not_called()

    def test_duplicate_model_mount_blocks_start(self):
        with patch.object(m.subprocess, 'check_output', return_value='other-server\n'), patch.object(m, 'inspect', return_value={'Mounts': [{'Source': str(m.MODEL)}]}):
            with self.assertRaises(m.LocalCodeError):
                m.ensure_server()
        m.subprocess.run.assert_not_called()

    def test_start_reuses_stopped_container(self):
        with patch.object(m.subprocess, 'check_output', return_value=''), patch.object(m, 'managed', return_value=self.state(False)), patch.object(m, 'validate'), patch.object(m, 'wait_for_server') as wait, patch.object(m.subprocess, 'run') as run:
            m.ensure_server()
            run.assert_called_once_with(['docker', 'start', m.CONTAINER], check=True)
            wait.assert_called_once()

    def test_start_reuses_running_compatible_container_without_mutation(self):
        with patch.object(m.subprocess, 'check_output', side_effect=[m.CONTAINER + '\n', 'sha256:fixture']), patch.object(m, 'managed', return_value=self.state()), patch.object(m, 'wait_for_server'):
            m.ensure_server()
        m.subprocess.run.assert_not_called()

    def test_incompatible_timeout_never_triggers_replacement(self):
        for running in (True, False):
            for old in (None, '3600'):
                with self.subTest(running=running, timeout=old):
                    state = self.state(running)
                    cmd = state['Config']['Cmd']
                    pos = cmd.index('--timeout')
                    if old is None:
                        del cmd[pos:pos+2]
                    else:
                        cmd[pos+1] = old
                    with patch.object(m.subprocess, 'check_output', return_value=m.CONTAINER + '\n'), patch.object(m, 'managed', return_value=state), patch.object(m, 'wait_for_server') as wait:
                        with self.assertRaises(m.LocalCodeError):
                            m.ensure_server()
                        wait.assert_not_called()
        m.subprocess.run.assert_not_called()  # no start, stop, rm, rename, run.

    def test_restart_rejects_incompatible_container_before_stop(self):
        state = self.state()
        state['Config']['Cmd'] = state['Config']['Cmd'][:-2]
        with patch.object(m.sys, 'argv', ['localcode.py', 'restart']), patch.object(m, 'managed', return_value=state):
            with self.assertRaises(m.LocalCodeError):
                m.main()
        m.subprocess.run.assert_not_called()
