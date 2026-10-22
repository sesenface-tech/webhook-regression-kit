import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from delivery_probe.demo import EVENTS, receiver
from webhook_regression_kit.cli import main
from webhook_regression_kit.generator import Redactor, generate


EXPECTED = {"processed_unique": 2, "version": 2}


class GeneratorTests(unittest.TestCase):
    def test_redacts_nested_fields_and_preserves_input(self):
        events = [{"id": "a", "nested": {"api_key": "example-private", "email": "owner@example.invalid"}}, {"id": "b"}]
        before = json.dumps(events)
        source, summary = generate(events, EXPECTED)
        self.assertNotIn("example-private", source)
        self.assertNotIn("owner@example.invalid", source)
        self.assertEqual(json.dumps(events), before)
        self.assertEqual(summary['redaction_occurrences'], 2)
        self.assertTrue(summary['manual_review_required'])

    def test_patterns_and_explicit_values(self):
        value = 'owner@example.invalid https://host.invalid/path?key=example Bearer abc.def.ghi custom-value'
        result = Redactor(['custom-value']).clean({'message': value})
        text = json.dumps(result)
        for raw in ('owner@example.invalid', 'host.invalid', 'abc.def.ghi', 'custom-value'):
            self.assertNotIn(raw, text)

    def test_private_key_and_token_patterns(self):
        key = '-----BEGIN PRIVATE KEY-----\nexample\n-----END PRIVATE KEY-----'
        token = 'ghp_' + 'x' * 24
        source, _ = generate([{'id': 'a', 'notes': key + ' ' + token}], EXPECTED, 'normal')
        self.assertNotIn('BEGIN PRIVATE KEY', source)
        self.assertNotIn(token, source)

    def test_stable_placeholders_and_expected_state(self):
        redactor = Redactor()
        events = redactor.clean([{'email': 'a@example.invalid'}, {'email': 'a@example.invalid'}, {'email': 'b@example.invalid'}])
        expected = redactor.clean({'email': 'a@example.invalid'})
        self.assertEqual(events[0]['email'], events[1]['email'])
        self.assertEqual(events[0]['email'], expected['email'])
        self.assertNotEqual(events[0]['email'], events[2]['email'])

    def test_rejects_redacted_key_collisions(self):
        with self.assertRaises(ValueError):
            Redactor().clean({'a@example.invalid': 1, 'REDACTED_0001': 2})

    def test_source_is_data_not_executable_interpolation(self):
        value = "'); raise RuntimeError('injected') #\n\\ triple ''' end"
        source, _ = generate([{'id': 'a', 'payload': value}], EXPECTED, 'normal')
        tree = ast.parse(source)
        case_assign = next(n for n in tree.body if isinstance(n, ast.Assign))
        encoded = ast.literal_eval(case_assign.value.args[0])
        self.assertEqual(json.loads(encoded)['events'][0]['payload'], value)
        self.assertEqual(source, generate([{'id': 'a', 'payload': value}], EXPECTED, 'normal')[0])

    def test_validation(self):
        for events, expected, scenario in [([], EXPECTED, 'normal'), (EVENTS, {}, 'normal'), (EVENTS, EXPECTED, 'invalid'), ([{'id': 'a'}, {'id': 'a'}], EXPECTED, 'duplicate'), ([{'id': 'a'}], EXPECTED, 'delayed')]:
            with self.assertRaises(ValueError):
                generate(events, expected, scenario)
        for delay in (float('nan'), float('inf'), -1, 6, True):
            with self.assertRaises(ValueError):
                generate(EVENTS, EXPECTED, delay=delay)
        with self.assertRaises(ValueError):
            generate(EVENTS, EXPECTED, explicit=[''])

    def test_cli_writes_restrictively_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events, expected, output = root/'events.json', root/'state.json', root/'test_case.py'
            events.write_text(json.dumps(EVENTS))
            expected.write_text(json.dumps(EXPECTED))
            args = ['--events', str(events), '--expected', str(expected), '--output', str(output)]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args), 0)
            self.assertNotIn(str(root), out.getvalue())
            original = output.read_bytes()
            if os.name == 'posix':
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertEqual(original, output.read_bytes())

    def test_symlink_destination_is_rejected(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('No symlinks')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target, link = root/'events.json', root/'state.json', root/'link.py'
            source.write_text(json.dumps(EVENTS))
            target.write_text(json.dumps(EXPECTED))
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            before = target.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--events', str(source), '--expected', str(target), '--output', str(link)]), 2)
            self.assertEqual(before, target.read_bytes())

    def test_generated_regressions_with_real_local_http(self):
        # Application-level execution of generated artifacts, not a mocked replay.
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join(str(Path(p or '.').resolve()) for p in sys.path)
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            for robust in (False, True):
                for scenario in ('normal', 'duplicate', 'delayed', 'reorder'):
                    source, _ = generate(EVENTS, EXPECTED, scenario, delay=.01)
                    test_file = Path(directory)/'test_generated.py'
                    test_file.write_text(source)
                    with receiver(robust) as base:
                        env['WEBHOOK_TARGET'] = base + '/webhook'
                        env['WEBHOOK_STATE_URL'] = base + '/state'
                        result = subprocess.run([sys.executable, str(test_file)], env=env, capture_output=True, text=True, timeout=15)
                    wanted = 1 if not robust and scenario in ('duplicate', 'reorder') else 0
                    self.assertEqual(result.returncode, wanted, result.stderr)
                    outcomes.append(result.returncode)
        self.assertEqual(outcomes, [0, 1, 0, 1, 0, 0, 0, 0])

    def test_missing_receiver_config_fails_instead_of_skipping(self):
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join(str(Path(p or '.').resolve()) for p in sys.path)
        env.pop('WEBHOOK_TARGET', None)
        env.pop('WEBHOOK_STATE_URL', None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test_generated.py'
            path.write_text(generate(EVENTS, EXPECTED)[0])
            result = subprocess.run([sys.executable, str(path)], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('skipped', result.stderr)


if __name__ == '__main__':
    unittest.main()
