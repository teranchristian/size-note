import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


@dataclass
class InstallerSandbox:
    project: Path
    home: Path
    env: dict[str, str]
    profile: str

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.project / "install.sh"), *arguments],
            cwd=self.project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    @property
    def bin_dir(self) -> Path:
        return Path(self.env["XDG_BIN_HOME"])

    @property
    def profile_home(self) -> Path:
        if self.profile == "default":
            return self.home / ".hermes"
        return self.home / ".hermes" / "profiles" / self.profile


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _create_sandbox(
    tmp_path: Path,
    *,
    profile: str = "example-profile",
    backend: str = "local",
    with_hermes: bool = True,
) -> InstallerSandbox:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy2(PROJECT_ROOT / "install.sh", project / "install.sh")
    shutil.copy2(PROJECT_ROOT / ".env.example", project / ".env.example")
    shutil.copy2(PROJECT_ROOT / "requirements.lock", project / "requirements.lock")
    skill_source = project / "integrations" / "hermes"
    skill_source.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "integrations/hermes/SKILL.md", skill_source / "SKILL.md")
    (project / ".env").write_text("SIZE_NOTE_PORT=4321\n")

    home = tmp_path / "home"
    home.mkdir()
    if profile == "default":
        profile_home = home / ".hermes"
    else:
        profile_home = home / ".hermes" / "profiles" / profile
    profile_home.mkdir(parents=True)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env sh
set -eu
printf 'port=%s args=%s\\n' "${SIZE_NOTE_PORT:-}" "$*" >>"$FAKE_DOCKER_LOG"
""",
    )
    _write_executable(
        fake_bin / "python3",
        """#!/usr/bin/env sh
set -eu
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
  target=$3
  mkdir -p "$target/bin"
  cp "$0" "$target/bin/python"
  printf '%s\\n' \\
    '#!/usr/bin/env sh' \\
    'printf "%s\\n" "${SIZE_NOTE_URL:-missing}"' >"$target/bin/size-note"
  chmod 755 "$target/bin/python" "$target/bin/size-note"
  exit 0
fi
""",
    )
    if with_hermes:
        _write_executable(
            fake_bin / "hermes",
            """#!/usr/bin/env sh
set -eu
if [ "${1:-}" = "profile" ] && [ "${2:-}" = "show" ]; then
  requested=$3
  [ "$requested" = "$FAKE_HERMES_PROFILE" ] || exit 1
  if [ "$requested" = "default" ]; then
    target="$HOME/.hermes"
  else
    target="$HOME/.hermes/profiles/$requested"
  fi
  printf 'Profile: %s\\nPath:    %s\\n' "$requested" "$target"
  exit 0
fi
if [ "${1:-}" = "-p" ]; then
  requested=$2
  shift 2
  [ "$requested" = "$FAKE_HERMES_PROFILE" ] || exit 1
fi
if [ "${1:-}" = "config" ] && [ "${2:-}" = "get" ]; then
  printf '%s\\n' "$FAKE_HERMES_BACKEND"
  exit 0
fi
if [ "${1:-}" = "skills" ] && [ "${2:-}" = "list" ]; then
  if [ "$FAKE_HERMES_PROFILE" = "default" ]; then
    target="$HOME/.hermes"
  else
    target="$HOME/.hermes/profiles/$FAKE_HERMES_PROFILE"
  fi
  [ -f "$target/skills/size-note/SKILL.md" ] && printf '%s\\n' 'size-note'
  exit 0
fi
exit 1
""",
        )

    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "TMPDIR": str(tmp_path),
        "XDG_BIN_HOME": str(tmp_path / "bin"),
        "XDG_DATA_HOME": str(tmp_path / "data-home"),
        "FAKE_DOCKER_LOG": str(docker_log),
        "FAKE_HERMES_PROFILE": profile,
        "FAKE_HERMES_BACKEND": backend,
    }
    return InstallerSandbox(project=project, home=home, env=env, profile=profile)


def test_installs_named_profile_and_is_safe_to_rerun(tmp_path):
    sandbox = _create_sandbox(tmp_path)
    preserved = sandbox.project / "data" / "preserved.txt"

    first = sandbox.run("--profile", sandbox.profile)
    preserved.write_text("keep")
    second = sandbox.run("--profile", sandbox.profile)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert preserved.read_text() == "keep"
    assert (sandbox.profile_home / "skills/size-note/SKILL.md").is_file()
    assert "Installed and verified Hermes skill" in second.stdout
    assert "start a new session" in second.stdout
    cli = subprocess.run(
        [str(sandbox.bin_dir / "size-note"), "health"],
        env=sandbox.env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert cli.stdout.strip() == "http://127.0.0.1:4321"


def test_default_profile_uses_default_hermes_home(tmp_path):
    sandbox = _create_sandbox(tmp_path, profile="default")

    result = sandbox.run()

    assert result.returncode == 0, result.stderr
    assert (sandbox.home / ".hermes/skills/size-note/SKILL.md").is_file()
    assert not (sandbox.home / ".hermes/profiles/default").exists()


def test_rejects_unknown_profile_before_starting_docker(tmp_path):
    sandbox = _create_sandbox(tmp_path)

    result = sandbox.run("--profile", "missing-profile")

    assert result.returncode == 1
    assert "Hermes profile not found" in result.stderr
    docker_log = Path(sandbox.env["FAKE_DOCKER_LOG"]).read_text()
    assert "up -d --build" not in docker_log


def test_rejects_non_local_hermes_terminal_backend(tmp_path):
    sandbox = _create_sandbox(tmp_path, backend="docker")

    result = sandbox.run("--profile", sandbox.profile)

    assert result.returncode == 1
    assert "requires the local terminal backend" in result.stderr
    docker_log = Path(sandbox.env["FAKE_DOCKER_LOG"]).read_text()
    assert "up -d --build" not in docker_log


def test_no_skill_install_does_not_require_hermes(tmp_path):
    sandbox = _create_sandbox(tmp_path, with_hermes=False)

    result = sandbox.run("--no-skill")

    assert result.returncode == 0, result.stderr
    assert "Size Note is ready" in result.stdout


def test_environment_port_configures_compose_and_cli(tmp_path):
    sandbox = _create_sandbox(tmp_path)
    sandbox.env["SIZE_NOTE_PORT"] = "5432"

    result = sandbox.run("--profile", sandbox.profile)

    assert result.returncode == 0, result.stderr
    docker_log = Path(sandbox.env["FAKE_DOCKER_LOG"]).read_text()
    assert "port=5432" in docker_log
    cli = subprocess.run(
        [str(sandbox.bin_dir / "size-note"), "health"],
        env={key: value for key, value in sandbox.env.items() if key != "SIZE_NOTE_PORT"},
        text=True,
        capture_output=True,
        check=True,
    )
    assert cli.stdout.strip() == "http://127.0.0.1:5432"
