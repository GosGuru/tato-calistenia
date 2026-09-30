"""Synthetic, mocked CLI contracts; never invokes a model."""
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch as mock_patch

from tools.editorial_rag.codex_runner import (  # pyright: ignore[reportMissingImports]
    CodexRunnerError,
    CodexSessionRunner,
)
from tools.editorial_rag.prototype import (  # pyright: ignore[reportMissingImports]
    Conversation,
    Message,
    packets,
)


# Keep patch targets package-qualified for both discovery and dotted invocation.
def patch(target, **kwargs):
    return mock_patch('tools.editorial_rag.' + target, **kwargs)


DESCRIPTION_WARNINGS = (
    'Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.',
    'Skill descriptions were shortened to fit the 2% skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.',
)


def warning_event(message=DESCRIPTION_WARNINGS[0]):
    return {'type': 'item.completed',
            'item': {'id': 'synthetic-warning', 'type': 'error', 'message': message}}


def stream(*items):
    return '\n'.join(json.dumps(x) for x in items)


def success(text='qué querés lograr?'):
    return stream({'type': 'thread.started', 'thread_id': 'synthetic'},
                  {'type': 'turn.started'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}},
                  {'type': 'turn.completed', 'usage': {}})


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.packet = packets(Conversation(
            sanitized=True, phase='brecha', gate='normal', situation='respuesta breve',
            last_assistant_move='validation', messages=(Message('user', 'sí'),)),
            (), 'CURRENT RULES')[0]
        original = tempfile.TemporaryDirectory
        temporary = patch('codex_runner.tempfile.TemporaryDirectory',
                          side_effect=lambda **kw: original(**kw))
        temporary.start()
        self.addCleanup(temporary.stop)

    def invoke(self, output=None, failure=None, returncode=0):
        seen = []
        def run(args, **kwargs):
            seen.append((args, kwargs))
            if 'status' in args:
                return subprocess.CompletedProcess(args, 0, '', 'Logged in using ChatGPT\n')
            self.assertTrue(Path(kwargs['cwd']).is_dir())
            self.assertEqual(list(Path(kwargs['cwd']).iterdir()), [])
            if failure:
                raise failure
            return subprocess.CompletedProcess(args, returncode, output or success(), '')
        with patch('codex_runner.shutil.which', return_value='/synthetic/codex'), \
             patch('codex_runner.subprocess.run', side_effect=run):
            result = CodexSessionRunner()(self.packet)
        return result, seen

    def test_diagnostics_login_failures_never_attempt_exec_or_retain_context(self):
        from tools.editorial_rag.generation_diagnostics import (  # pyright: ignore[reportMissingImports]
            GenerationDiagnostics,
        )

        for response, expected in (
            (subprocess.CompletedProcess([], 0, 'secret-sentinel', ''), 'rejected'),
            (subprocess.TimeoutExpired(['secret-sentinel'], 1, output='secret-sentinel'), 'timeout'),
        ):
            diagnostics = GenerationDiagnostics()
            with patch('codex_runner.shutil.which', return_value='/fictional/codex'), \
                    patch('codex_runner.subprocess.run', side_effect=[response]) as run, \
                    self.assertRaises(CodexRunnerError) as caught:
                CodexSessionRunner(diagnostics=diagnostics)(self.packet)
            self.assertEqual(run.call_count, 1)
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(diagnostics.headers()['X-Tato-Login-Outcome'], expected)
            self.assertEqual(diagnostics.headers()['X-Tato-Exec-Attempts'], '0')
            self.assertNotIn('secret-sentinel', repr(vars(diagnostics)))
        diagnostics = GenerationDiagnostics()
        with patch('codex_runner.shutil.which', return_value=None), \
                patch('codex_runner.subprocess.run') as run, self.assertRaises(CodexRunnerError):
            CodexSessionRunner(diagnostics=diagnostics)(self.packet)
        run.assert_not_called()
        self.assertEqual(diagnostics.headers()['X-Tato-Login-Outcome'], 'unavailable')
        self.assertEqual(diagnostics.headers()['X-Tato-Exec-Attempts'], '0')

    def test_flags_stdin_final_and_disposal(self):
        result, seen = self.invoke()
        self.assertEqual(result, 'qué querés lograr?')
        args, kw = seen[-1]
        for flag in ('--json', '--ephemeral', '--ignore-user-config', '--skip-git-repo-check'):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
        self.assertEqual(args[args.index('-C') + 1], kw['cwd'])
        self.assertEqual(args[-1], '-')
        self.assertFalse(Path(kw['cwd']).exists())
        self.assertIn('CURRENT RULES', kw['input'])
        self.assertIn('untrusted', kw['input'])
        self.assertNotIn(kw['input'], repr(args))
        self.assertFalse(kw['shell'])
        self.assertNotIn('OPENAI_API_KEY', kw['env'])
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('voice only', kw['input'])
        self.assertIn('exactly one next Instagram DM', kw['input'])

    def test_exact_description_warnings_allow_complete_final(self):
        for message in DESCRIPTION_WARNINGS:
            with self.subTest(message=message):
                self.assertEqual(self.invoke(stream(warning_event(message)) + '\n' + success())[0],
                                 'qué querés lograr?')

    def test_description_warning_exception_is_exact_and_fail_closed(self):
        known = warning_event()
        final = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'draft'}}
        completed = {'type': 'turn.completed'}
        tool = {'type': 'item.started', 'item': {'type': 'command_execution'}}
        messages = (' ' + DESCRIPTION_WARNINGS[0], DESCRIPTION_WARNINGS[0] + ' ',
                    'Warning: ' + DESCRIPTION_WARNINGS[0], DESCRIPTION_WARNINGS[0] + ' Extra.',
                    DESCRIPTION_WARNINGS[0].lower(), DESCRIPTION_WARNINGS[0][:-1],
                    DESCRIPTION_WARNINGS[0].replace('2%', '3%').replace('the skills', 'the 3% skills'),
                    'Harmless catalogue warning', 'Dropped events from event stream',
                    'Task instructions were truncated', 'Invalid rules', 'Authentication failed')
        outputs = [stream(warning_event(message), final, completed) for message in messages]
        outputs += [stream(known, completed), stream(known, final),
                    stream(known, final, completed, known),
                    stream(tool, known, final, completed), stream(known, tool, final, completed),
                    stream({'type': 'error', 'message': DESCRIPTION_WARNINGS[0]}, final, completed),
                    stream(known, final, {'type': 'turn.failed'}),
                    stream(known, final, completed) + '\ninvalid']
        for kind in ('item.started', 'item.updated'):
            outputs.append(stream(known | {'type': kind}, final, completed))
        for item in ({'type': 'error', 'message': DESCRIPTION_WARNINGS[0]},
                     known['item'] | {'id': None}, known['item'] | {'id': ''},
                     known['item'] | {'message': [DESCRIPTION_WARNINGS[0]]},
                     known['item'] | {'tool': 'command_execution'}):
            outputs.append(stream(known | {'item': item}, final, completed))
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(CodexRunnerError) as ctx:
                self.invoke(output)
            self.assertIsNone(ctx.exception.__context__)
            self.assertNotIn('draft', str(ctx.exception).replace('no draft returned', ''))
        with self.assertRaises(CodexRunnerError):
            self.invoke(stream(known, final, completed), returncode=1)

    def test_reviewed_history_uses_same_strict_runner(self):
        from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
            RealPacket,
            parse_history,
        )

        self.packet = RealPacket(parse_history('Prospecto: texto ficticio'), 'CURRENT RULES', True, True)
        result, seen = self.invoke()
        self.assertEqual(result, 'qué querés lograr?')
        self.assertEqual(len(seen), 2)  # Auth check plus one generation, never a pair.
        args, options = seen[-1]
        self.assertIn('--ephemeral', args)
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('UNTRUSTED HISTORY JSON', options['input'])
        self.assertNotIn('voice_guidance', options['input'])
        for output in (stream({'type': 'item.started', 'item': {'type': 'command_execution'}}) + '\n' + success(),
                       stream({'type': 'error', 'message': 'fictional diagnostic'}),
                       stream({'type': 'turn.completed'})):
            with self.assertRaises(CodexRunnerError):
                self.invoke(output)
        with patch('codex_runner.subprocess.run') as run, self.assertRaises(CodexRunnerError):
            CodexSessionRunner()(replace(self.packet, reviewed=1))
        run.assert_not_called()

    def test_organization_dispatch_retains_strict_session_contract(self):
        from tools.editorial_rag.organization import (  # pyright: ignore[reportMissingImports]
            OrganizationPacket,
            parse_blocks,
        )
        from tools.editorial_rag.test_organization import (  # pyright: ignore[reportMissingImports]
            blocks,
        )

        self.packet = OrganizationPacket(parse_blocks(blocks()), True, True)
        final = '{"assignments":[]}'
        result, seen = self.invoke(success(final))
        self.assertEqual(result, final)  # Coverage is validated by the route, not JSONL transport.
        self.assertEqual(len(seen), 2)
        self.assertIn('speaker assignments only', seen[-1][1]['input'])
        self.assertNotIn('CURRENT RULES', seen[-1][1]['input'])
        self.assertIn('--ephemeral', seen[-1][0])
        for key in ('reviewed', 'consent'):
            with patch('codex_runner.subprocess.run') as run, self.assertRaises(CodexRunnerError):
                CodexSessionRunner()(replace(self.packet, **{key: False}))
            run.assert_not_called()
        for output in (stream({'type': 'item.started', 'item': {'type': 'command_execution'}}) + '\n' + success(final),
                       stream({'type': 'turn.failed'}), stream({'type': 'turn.completed'})):
            with self.assertRaises(CodexRunnerError):
                self.invoke(output)
        for warning in DESCRIPTION_WARNINGS:
            self.assertEqual(self.invoke(stream(warning_event(warning)) + '\n' + success(final))[0], final)

    def test_raw_dispatch_uses_one_ephemeral_generation(self):
        from tools.editorial_rag.raw_history import (  # pyright: ignore[reportMissingImports]
            RawHistoryPacket,
        )

        self.packet = RawHistoryPacket('  ficticio\r\nrepetido\nrepetido', 'CURRENT RULES', True)
        final = '{"type":"needs_context","question":"quién responde?"}'
        result, seen = self.invoke(success(final))
        self.assertEqual(result, final)
        self.assertEqual(len(seen), 2)
        self.assertEqual(sum('exec' in args for args, _ in seen), 1)
        self.assertIn('UNTRUSTED RAW HISTORY JSON', seen[-1][1]['input'])
        self.assertIn('--ephemeral', seen[-1][0])
        self.assertNotIn('voice_guidance', seen[-1][1]['input'])
        with patch('codex_runner.subprocess.run') as run, self.assertRaises(CodexRunnerError):
            CodexSessionRunner()(replace(self.packet, consent=1))
        run.assert_not_called()
        with self.assertRaises(CodexRunnerError):
            self.invoke(stream({'type': 'item.started', 'item': {'type': 'command_execution'}}) + '\n' + success(final))

    def test_last_message_only(self):
        text = stream({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'first'}},
                      {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'last'}},
                      {'type': 'turn.completed'})
        self.assertEqual(self.invoke(text)[0], 'last')

    def test_malformed_error_tool_unknown_and_incomplete_fail_closed(self):
        for output in ('not json', '[]', '{}', success() + '\ninvalid',
                       stream({'type': 'error', 'message': 'PRIVATE'}),
                       stream({'type': 'turn.failed'}),
                       stream({'type': 'item.started', 'item': {'type': 'command_execution'}}),
                       stream({'type': 'item.completed', 'item': {'type': 'mcp_tool_call'}}),
                       stream({'type': 'new.event'}),
                       stream({'type': 'turn.completed'}),
                       stream({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'draft'}})):
            with self.subTest(output=output), self.assertRaises(CodexRunnerError) as ctx:
                self.invoke(output)
            self.assertNotIn('PRIVATE', str(ctx.exception))

    def test_timeout_redacts_and_disposes(self):
        paths = []
        def run(args, **kwargs):
            paths.append(kwargs['cwd'])
            raise subprocess.TimeoutExpired(args, 1, output='SECRET', stderr='SECRET')
        with patch('codex_runner.shutil.which', return_value='/synthetic/codex'), \
             patch('codex_runner.subprocess.run', side_effect=run), \
             self.assertRaises(CodexRunnerError) as ctx:
            CodexSessionRunner()(self.packet)
        self.assertNotIn('SECRET', str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)
        self.assertTrue(all(not Path(p).exists() for p in paths))

    def test_generation_timeout_has_no_sensitive_exception_context(self):
        paths = []
        def run(args, **kwargs):
            paths.append(kwargs['cwd'])
            if 'status' in args:
                return subprocess.CompletedProcess(args, 0, 'Logged in using ChatGPT', '')
            raise subprocess.TimeoutExpired(args + [kwargs['input']], 1,
                                            output='PRIVATE OUTPUT', stderr='PRIVATE STDERR')
        with patch('codex_runner.shutil.which', return_value='/synthetic/codex'), \
             patch('codex_runner.subprocess.run', side_effect=run), \
             self.assertRaises(CodexRunnerError) as ctx:
            CodexSessionRunner()(self.packet)
        self.assertIsNone(ctx.exception.__context__)
        self.assertNotIn('CURRENT RULES', repr(ctx.exception))
        self.assertNotIn('PRIVATE', repr(ctx.exception))
        self.assertTrue(all(not Path(p).exists() for p in paths))

    def test_all_tool_item_kinds_rejected(self):
        for kind in ('command_execution', 'file_change', 'mcp_tool_call',
                     'web_search', 'todo_list', 'unknown_tool'):
            with self.subTest(kind=kind), self.assertRaises(CodexRunnerError):
                self.invoke(stream({'type': 'item.completed', 'item': {'type': kind}})
                            + '\n' + success())

    def test_missing_cli_auth_and_nonzero(self):
        with patch('codex_runner.shutil.which', return_value=None), self.assertRaises(CodexRunnerError):
            CodexSessionRunner()(self.packet)
        for status in (subprocess.CompletedProcess([], 1, 'SECRET', 'SECRET'),
                       subprocess.CompletedProcess([], 0, 'Logged in using an API key', '')):
            with patch('codex_runner.shutil.which', return_value='/synthetic/codex'), \
                 patch('codex_runner.subprocess.run', return_value=status), \
                 self.assertRaises(CodexRunnerError):
                CodexSessionRunner()(self.packet)
        with patch('codex_runner.shutil.which', return_value='/synthetic/codex'), \
             patch('codex_runner.subprocess.run', side_effect=[
                 subprocess.CompletedProcess([], 0, 'Logged in using ChatGPT', ''),
                 subprocess.CompletedProcess([], 1, success(), 'SECRET')]), \
             self.assertRaises(CodexRunnerError):
            CodexSessionRunner()(self.packet)

    def test_invalid_packet_before_process(self):
        with patch('codex_runner.subprocess.run') as run, self.assertRaises(CodexRunnerError):
            CodexSessionRunner()(replace(self.packet, variant='other'))
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
