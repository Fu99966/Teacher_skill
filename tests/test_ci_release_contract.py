from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_cross_platform_release_gates():
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert 'python-version: "3.10"' in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'python-version: "3.12"' in workflow
    assert 'python-version: "3.13"' in workflow
    assert "ubuntu-latest" in workflow
    assert "windows-latest" in workflow
    assert "python -m compileall teacher_agent" in workflow
    assert "node --check web/static/app.js" in workflow
    assert "python -m teacher_agent.cli scan-template templates/sample_lesson_template.docx" in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m pip check" in workflow


def test_runtime_agent_artifacts_are_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    rules = {line.strip() for line in gitignore.splitlines()}

    assert "outputs/" in rules


def test_runtime_outputs_are_not_tracked_by_git():
    tracked = subprocess.run(
        ["git", "ls-files", "outputs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()

    assert tracked == ""
