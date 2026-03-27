from __future__ import annotations

import subprocess

from mixedsig2cad import dev_env


def test_parse_node_version_accepts_semver_output() -> None:
    assert dev_env.parse_node_version("v18.20.4\n") == (18, 20, 4)


def test_parse_node_version_rejects_invalid_output() -> None:
    assert dev_env.parse_node_version("node version") is None


def test_find_browser_executable_prefers_env_var(monkeypatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/tmp/custom-browser")
    monkeypatch.setattr(dev_env.Path, "exists", lambda self: str(self) == "/tmp/custom-browser")

    assert dev_env.find_browser_executable() == "/tmp/custom-browser"


def test_frontend_runtime_issues_reports_missing_npm_packages(monkeypatch) -> None:
    monkeypatch.setattr(dev_env.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(dev_env, "node_version_error", lambda: None)
    monkeypatch.setattr(dev_env, "npm_packages_available", lambda: False)

    assert dev_env.frontend_runtime_issues() == ["frontend npm packages"]


def test_frontend_runtime_issues_accepts_playwright_browser_download(monkeypatch) -> None:
    monkeypatch.setattr(dev_env.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(dev_env, "node_version_error", lambda: None)
    monkeypatch.setattr(dev_env, "npm_packages_available", lambda: True)
    monkeypatch.setattr(dev_env, "find_browser_executable", lambda: None)
    monkeypatch.setattr(dev_env, "playwright_browser_available", lambda: True)

    assert dev_env.frontend_runtime_issues() == []


def test_node_version_error_reports_old_node(monkeypatch) -> None:
    monkeypatch.setattr(dev_env, "node_version", lambda: (16, 19, 1))

    assert dev_env.node_version_error() == "node >= 18 (found 16.19.1)"


def test_npm_packages_available_runs_from_repo_root(monkeypatch) -> None:
    def fake_run(cmd, cwd, capture_output, text, check):
        assert cmd == ["node", "-e", "require('playwright'); require('@playwright/test');"]
        assert cwd == dev_env.ROOT
        assert capture_output is True
        assert text is True
        assert check is False
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(dev_env.subprocess, "run", fake_run)

    assert dev_env.npm_packages_available() is True


def test_playwright_browser_available_checks_downloaded_browser(monkeypatch) -> None:
    def fake_run(cmd, cwd, capture_output, text, check):
        assert cmd[0:2] == ["node", "-e"]
        assert "chromium.executablePath" in cmd[2]
        assert cwd == dev_env.ROOT
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(dev_env.subprocess, "run", fake_run)

    assert dev_env.playwright_browser_available() is True
