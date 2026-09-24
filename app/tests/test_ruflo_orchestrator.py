from pathlib import Path

import pytest

from scorpion.ruflo_orchestrator import RufloCommandError, RufloOrchestrator


class FakeRunner:
    def __init__(self, *, version="ruflo 3.test", fail_on=None):
        self.calls = []
        self.version = version
        self.fail_on = fail_on

    def __call__(self, command, cwd, timeout):
        command = tuple(command)
        self.calls.append((command, cwd, timeout))
        if self.fail_on and self.fail_on in command:
            return 1, "", "synthetic failure"
        if command[-1] == "--version":
            return 0, self.version, ""
        return 0, "ok", ""


def test_status_uses_local_command_without_installing_anything(tmp_path):
    runner = FakeRunner()
    bridge = RufloOrchestrator(command="ruflo", cwd=tmp_path, runner=runner)

    status = bridge.status()

    assert status.available is True
    assert status.version == "ruflo 3.test"
    assert runner.calls[0][0] == ("ruflo", "--version")
    assert runner.calls[0][1] == Path(tmp_path)


def test_prepare_task_creates_coder_tester_and_supported_update_reviewer(tmp_path):
    runner = FakeRunner()
    bridge = RufloOrchestrator(command="ruflo", cwd=tmp_path, runner=runner, max_agents=4)

    plan = bridge.prepare_task("Verbessere die Wakeword-Erkennung")

    commands = [call[0] for call in runner.calls]
    assert ("ruflo", "agent", "spawn", "-t", "coder", "--name", "scorpion-coder") in commands
    assert ("ruflo", "agent", "spawn", "-t", "tester", "--name", "scorpion-tester") in commands
    assert (
        "ruflo",
        "agent",
        "spawn",
        "-t",
        "reviewer",
        "--name",
        "scorpion-update",
    ) in commands
    assert commands[-1][-2:] == (
        "--description",
        "Verbessere die Wakeword-Erkennung",
    )
    assert plan.requires_approval_to_apply is True
    assert plan.agents == ("scorpion-coder", "scorpion-tester", "scorpion-update")


def test_disabled_ruflo_never_runs_commands(tmp_path):
    runner = FakeRunner()
    bridge = RufloOrchestrator(enabled=False, cwd=tmp_path, runner=runner)

    with pytest.raises(RufloCommandError):
        bridge.prepare_task("Test")

    assert runner.calls == []


def test_failed_ruflo_command_is_reported(tmp_path):
    runner = FakeRunner(fail_on="swarm")
    bridge = RufloOrchestrator(cwd=tmp_path, runner=runner)

    with pytest.raises(RufloCommandError, match="synthetic failure"):
        bridge.prepare_task("Test")
