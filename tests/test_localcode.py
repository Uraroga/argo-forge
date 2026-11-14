import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('localcode', Path(__file__).parents[1] / 'localcode.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SafetyTests(unittest.TestCase):
    def test_fixed_server_contract(self):
        cmd = m.server_command()
        self.assertEqual(cmd[cmd.index('--ctx-size')+1], '131072')
        self.assertEqual(cmd[cmd.index('-p')+1], '127.0.0.1:18080:8080')
        self.assertIn('readonly', cmd[cmd.index('--mount')+1])
        self.assertEqual(cmd[cmd.index('--n-gpu-layers')+1], '0')
        self.assertEqual(cmd[cmd.index('--parallel')+1], '1')
    def test_tool_permission(self):
        cfg = m.opencode_config('lfm', 24, 256)
        self.assertEqual(cfg['enabled_providers'], ['llama.cpp'])
        self.assertEqual(cfg['agent']['local-build']['permission']['shell'], 'ask')
        self.assertEqual(m.opencode_config('lfm', 8, 256, True)['agent']['local-build']['permission']['shell'], 'allow')
    def test_foreign_container_untouched(self):
        with patch.object(m, 'inspect', return_value={'Config': {'Labels': {}}}):
            with self.assertRaises(m.LocalCodeError): m.managed()
    def test_transient_health_errors(self):
        with patch.object(m, 'docker_inspect', return_value='true'), patch.object(m, 'endpoint', side_effect=[ConnectionResetError(), '{', '{"status":"ok"}']), patch.object(m.time, 'sleep'):
            m.wait_for_server()
    def test_invalid_mount_rejected(self):
        state = {'Config': {'Cmd': m.server_command()[m.server_command().index(m.IMAGE)+1:]},
                 'Mounts': [{'Source': str(m.MODEL), 'Destination': '/models/lfm25.gguf', 'RW': True}]}
        with self.assertRaises(m.LocalCodeError): m.validate(state)
    def test_invalid_binding_rejected(self):
        state = {'Config': {'Cmd': m.server_command()[m.server_command().index(m.IMAGE)+1:]},
                 'Mounts': [{'Source': str(m.MODEL), 'Destination': '/models/lfm25.gguf', 'RW': False}],
                 'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '18080'}]}}}
        with self.assertRaises(m.LocalCodeError): m.validate(state)
    def test_running_legacy_server_blocks_start(self):
        with patch.object(m.subprocess, 'check_output', return_value='llama-cpp-lfm25\n'), patch.object(m, 'inspect', return_value={'Mounts': []}), patch.object(m.subprocess, 'run') as run:
            with self.assertRaises(m.LocalCodeError): m.ensure_server()
            run.assert_not_called()
    def test_start_reuses_stopped_container(self):
        with patch.object(m.subprocess, 'check_output', return_value=''), patch.object(m, 'managed', return_value={'State': {'Running': False}}), patch.object(m, 'validate'), patch.object(m, 'wait_for_server') as wait, patch.object(m.subprocess, 'run') as run:
            m.ensure_server()
            run.assert_called_once_with(['docker', 'start', m.CONTAINER], check=True)
            wait.assert_called_once()
