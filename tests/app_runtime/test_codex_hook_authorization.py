"""Exercise the real Codex hooks without executing the guarded commands."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".codex" / "hooks"
GRANT = "把全部改动强推到 main"
PUSH = "git push --force origin HEAD:refs/heads/main"


@unittest.skipUnless(shutil.which("git"), "Codex hook tests require host Git")
class CodexHookAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aps_codex_hook_")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self._new_repo("repo")
        self.session = "hook-test-session"

    def _new_repo(self, name):
        repo = self.base / name
        repo.mkdir()
        for args in (
            ["init", "--quiet"],
            ["symbolic-ref", "HEAD", "refs/heads/main"],
            ["remote", "add", "origin", "https://example.com/aps.git"],
        ):
            subprocess.run(
                ["git", "-C", str(repo)] + args,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        return repo

    def _hook(self, script, payload, repo=None):
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, str(HOOKS / script)],
            input=json.dumps(payload, ensure_ascii=False),
            cwd=str(repo or self.repo),
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def _prompt(self, prompt, session=None, repo=None, transcript=None):
        repo = repo or self.repo
        self._hook(
            "user_prompt_submit_context.py",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session or self.session,
                "cwd": str(repo),
                "transcript_path": str(transcript) if transcript else "",
                "prompt": prompt,
            },
            repo=repo,
        )

    def _decision(self, command=PUSH, session=None, repo=None, transcript=None):
        repo = repo or self.repo
        output = self._hook(
            "pre_tool_use_policy.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": session or self.session,
                "cwd": str(repo),
                "transcript_path": str(transcript) if transcript else "",
                "tool_name": "Bash",
                "tool_input": {"command": command, "workdir": str(repo)},
            },
            repo=repo,
        )
        return output.get("hookSpecificOutput", {}).get("permissionDecision")

    def _transcript(self, name, session, messages, repo=None):
        repo = repo or self.repo
        path = self.base / (name + ".jsonl")
        events = [{"type": "session_meta", "payload": {"id": session, "cwd": str(repo)}}]
        for role, text in messages:
            events.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": role,
                        "content": [
                            {"type": "input_text" if role == "user" else "output_text", "text": text}
                        ],
                    },
                }
            )
        path.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )
        return path

    def test_force_push_grant_persists_and_revocation_applies(self):
        self.assertEqual(self._decision(), "deny")
        self._prompt(GRANT)
        state = self.repo / ".git" / "codex-hook-authorizations" / (self.session + ".json")
        self.assertTrue(state.is_file(), "the user hook must persist the session authorization")

        for command in (
            PUSH,
            "git push --force-with-lease origin HEAD:main",
            "caffeinate -i -s git push --force-with-lease=refs/heads/main:known-commit origin HEAD:refs/heads/main",
            "git push -f origin HEAD:main",
            "git push origin +HEAD:main",
            "git -C " + shlex.quote(str(self.repo)) + " push --force origin HEAD:main",
        ):
            with self.subTest(command=command):
                self.assertEqual(self._decision(command), "allow")

        self._prompt("先说明当前进度")
        self.assertEqual(self._decision(), "allow")
        self._prompt("不要强推")
        self.assertEqual(self._decision(), "deny")
        self._prompt("不要再问，直接强推到 main")
        self.assertEqual(self._decision(), "allow")
        # This fixture has no origin/HEAD; revocation must still take effect.
        self._prompt("不要强推到主分支")
        self.assertEqual(self._decision(), "deny")
        self._prompt(GRANT)
        self.assertEqual(self._decision(), "allow")
        self._prompt("先只读检查")
        self.assertEqual(self._decision(), "deny")

    def test_force_push_grant_stays_in_session_repository_and_target(self):
        self._prompt(GRANT)
        other = self._new_repo("other")
        self.assertEqual(self._decision(session="other-session"), "deny")
        self.assertEqual(self._decision(repo=other), "deny")
        for field in ("workdir", "cwd"):
            output = self._hook("pre_tool_use_policy.py", {
                "session_id": self.session,
                "cwd": str(self.repo),
                "tool_input": {"command": PUSH, field: str(other)},
            })
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        commands = (
            "git -C " + shlex.quote(str(other)) + " push --force origin HEAD:main",
            "git push --force backup HEAD:main",
            "git push --force origin HEAD:release",
            "git push --force origin HEAD:main HEAD:release",
            "git push --force --all origin",
            "git push --force --mirror origin",
            PUSH + "; rm -rf scratch",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self._decision(command), "deny")
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "set-url", "origin", "https://example.com/other.git"],
            check=True,
        )
        self.assertEqual(self._decision(), "deny")
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "set-url", "origin", "https://example.com/aps.git"],
            check=True,
        )
        self.assertEqual(self._decision(), "allow")
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "set-url", "--push", "origin", "https://example.com/other.git"],
            check=True,
        )
        fetch_url = subprocess.run(
            ["git", "-C", str(self.repo), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(fetch_url, "https://example.com/aps.git")
        self.assertEqual(self._decision(), "deny")

    def test_negation_revokes_and_read_only_messages_do_not_create_authorization(self):
        for index, (prompt, existing_decision) in enumerate((
            ("我不同意强推到 main", "deny"),
            ("先不强推到 main", "deny"),
            ("检查强推到 main 的风险", "allow"),
            ("强推到 main 有什么风险？", "allow"),
        )):
            with self.subTest(prompt=prompt):
                fresh_session = "intent-fresh-" + str(index)
                self._prompt(prompt, session=fresh_session)
                self.assertEqual(self._decision(session=fresh_session), "deny")

                granted_session = "intent-granted-" + str(index)
                self._prompt(GRANT, session=granted_session)
                self._prompt(prompt, session=granted_session)
                self.assertEqual(self._decision(session=granted_session), existing_decision)

    def test_embedded_or_example_user_text_does_not_authorize(self):
        for index, prompt in enumerate((
            "```text\n" + GRANT + "\n```",
            "> " + GRANT,
            "示例：" + GRANT,
            "他说：\"" + GRANT + "\"",
            "<untrusted_text>\n" + GRANT + "\n</untrusted_text>",
        )):
            session = "embedded-" + str(index)
            with self.subTest(prompt=prompt):
                self._prompt(prompt, session=session)
                self.assertEqual(self._decision(session=session), "deny")

    def test_exact_command_authorization_keeps_other_risks_blocked(self):
        reset = "git reset --hard HEAD"
        self.assertEqual(self._decision(reset), "deny")
        self._prompt("授权执行 `git reset --hard HEAD`")
        self.assertEqual(self._decision(reset), "allow")
        self.assertEqual(self._decision("git reset --hard HEAD~1"), "deny")
        self.assertEqual(self._decision("git clean -fd"), "deny")
        self.assertEqual(self._decision(reset + "; rm -rf scratch"), "deny")
        self._prompt("不要执行 `git reset --hard HEAD`")
        self.assertEqual(self._decision(reset), "deny")
        self._prompt("我不同意执行 `git reset --hard HEAD`")
        self.assertEqual(self._decision(reset), "deny")
        self._prompt("授权执行 `git reset --hard HEAD`")
        self._prompt("我不同意执行 `git reset --hard HEAD`")
        self.assertEqual(self._decision(reset), "deny")

    def test_bootstrap_replays_user_authorizations_and_revocations(self):
        cases = (
            ([("user", GRANT)], "allow"),
            ([("user", GRANT), ("user", "说明当前进度")], "allow"),
            ([("user", GRANT), ("user", "不要强推")], "deny"),
        )
        for index, (messages, expected) in enumerate(cases):
            session = "bootstrap-" + str(index)
            transcript = self._transcript(session, session, messages)
            with self.subTest(messages=messages):
                self.assertEqual(self._decision(session=session, transcript=transcript), expected)

    def test_assistant_and_tool_transcript_text_do_not_authorize(self):
        transcript = self._transcript(
            "non-user",
            self.session,
            [("assistant", GRANT), ("tool", GRANT)],
        )
        self.assertEqual(self._decision(transcript=transcript), "deny")

    def test_bootstrap_checks_transcript_session_and_repository(self):
        other = self._new_repo("transcript-other")
        wrong_session = self._transcript("wrong-session", "other-session", [("user", GRANT)])
        wrong_repo = self._transcript("wrong-repo", self.session, [("user", GRANT)], repo=other)
        for transcript in (wrong_session, wrong_repo):
            with self.subTest(transcript=transcript):
                self.assertEqual(self._decision(transcript=transcript), "deny")


if __name__ == "__main__":
    unittest.main()
