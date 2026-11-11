"""Unit tests for the version 1 configuration contract and the exported environment."""

from pathlib import Path

import pytest

from testforge.config import ConfigError, load_config
from testforge.environment import EXPORTED_KEYS, runtime_environment

FULL = """
version = 1
name = "sample-api"
compose_file = "compose.yaml"
test_paths = ["tests", "extra_test.py"]

[env]
SAMPLE_PORT = "18090"

[readiness]
compose_wait_timeout_seconds = 60
url = "http://127.0.0.1:18090/health"
timeout_seconds = 20

[reports]
directory = "out/reports"
"""

MINIMAL = """
version = 1
name = "sample-api"
compose_file = "compose.yaml"
test_paths = ["tests"]
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    root.mkdir()
    (root / "compose.yaml").write_text("services: {}\n")
    (root / "tests").mkdir()
    (root / "extra_test.py").write_text("")
    return root


def write(root: Path, text: str, name: str = "testforge.toml") -> Path:
    path = root / name
    path.write_text(text)
    return path


def test_config_01_full_config_loads_with_resolved_paths(project):
    config = load_config(write(project, FULL))
    assert config.version == 1 and config.name == "sample-api"
    assert config.config_dir == project.resolve()
    assert config.compose_file == (project / "compose.yaml").resolve()
    assert config.test_paths == ((project / "tests").resolve(), (project / "extra_test.py").resolve())
    assert dict(config.env) == {"SAMPLE_PORT": "18090"}
    assert config.readiness.compose_wait_timeout_seconds == 60
    assert config.readiness.url == "http://127.0.0.1:18090/health"
    assert config.readiness.timeout_seconds == 20
    assert config.reports_directory == (project / "out/reports").resolve()


def test_config_02_minimal_config_applies_defaults(project):
    config = load_config(write(project, MINIMAL))
    assert dict(config.env) == {}
    assert config.readiness.url is None
    assert config.readiness.compose_wait_timeout_seconds == 90
    assert config.readiness.timeout_seconds == 45
    assert config.reports_directory == (project / "reports").resolve()


def test_config_03_paths_resolve_from_config_directory_not_cwd(project, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load_config(write(project, MINIMAL))
    assert config.compose_file.parent == project.resolve()
    assert config.test_paths[0].parent == project.resolve()


def test_config_04_absolute_paths_are_kept(project, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    config = load_config(write(project, MINIMAL + f'\n[reports]\ndirectory = "{other}"\n'))
    assert config.reports_directory == other.resolve()


def test_config_05_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_config_06_unparseable_toml(project):
    with pytest.raises(ConfigError, match="Could not parse"):
        load_config(write(project, "version = \n"))


def test_config_07_retired_targets_format_is_explained(project):
    with pytest.raises(ConfigError, match="retired"):
        load_config(write(project, '[targets.demo]\nrevision = "abc"\n'))


@pytest.mark.parametrize("version", ["", "version = 2", 'version = "1"', "version = true", "version = 1.0"])
def test_config_08_unsupported_or_missing_version(project, version):
    with pytest.raises(ConfigError, match="version"):
        load_config(write(project, MINIMAL.replace("version = 1", version)))


@pytest.mark.parametrize("line", ['name = "sample-api"', 'compose_file = "compose.yaml"', 'test_paths = ["tests"]'])
def test_config_09_missing_required_setting(project, line):
    key = line.split(" = ")[0]
    with pytest.raises(ConfigError, match=f"Missing required setting: {key}"):
        load_config(write(project, MINIMAL.replace(line, "")))


@pytest.mark.parametrize("name", ['""', '"Sample"', '"a b"', '"-x"', '"a.b"', f'"{"x" * 41}"', "7"])
def test_config_10_invalid_name(project, name):
    with pytest.raises(ConfigError, match="name must be"):
        load_config(write(project, MINIMAL.replace('"sample-api"', name)))


def test_config_11_compose_file_must_exist_as_file(project):
    with pytest.raises(ConfigError, match="compose_file does not exist"):
        load_config(write(project, MINIMAL.replace("compose.yaml", "nope.yaml")))
    with pytest.raises(ConfigError, match="compose_file does not exist"):
        load_config(write(project, MINIMAL.replace("compose.yaml", "tests")))


@pytest.mark.parametrize("value", ["[]", '"tests"', "[1]", '["missing"]'])
def test_config_12_invalid_test_paths(project, value):
    with pytest.raises(ConfigError, match="test_paths"):
        load_config(write(project, MINIMAL.replace('["tests"]', value)))


@pytest.mark.parametrize("extra,match", [("colour = 1", "Unknown setting at top level: colour"), ("[readiness]\nretries = 3", "Unknown setting at readiness: retries"), ("[reports]\nformat = 'x'", "Unknown setting at reports: format"), ("[profiles.ui]\n", "profiles are not supported")])
def test_config_13_unknown_settings_are_rejected(project, extra, match):
    with pytest.raises(ConfigError, match=match):
        load_config(write(project, MINIMAL + "\n" + extra + "\n"))


@pytest.mark.parametrize("env,match", [('env = "x"', "env must be a table"), ("[env]\nlower = 'x'", "env key 'lower'"), ("[env]\n1X = 'x'", "env key '1X'"), ("[env]\nTESTFORGE_BASE_URL = 'x'", "reserved"), ("[env]\nPORT = 18090", "env.PORT must be a string")])
def test_config_14_invalid_env(project, env, match):
    with pytest.raises(ConfigError, match=match):
        load_config(write(project, MINIMAL + "\n" + env + "\n"))


@pytest.mark.parametrize("url", ['"file:///etc/passwd"', '"http://user:secret@localhost"', '"http://localhost:bad"', '"http://localhost:70000"', '"http://localhost?token=secret"', '"http://localhost#x"', '"localhost:8080"', "8080"])
def test_config_15_invalid_readiness_url(project, url):
    with pytest.raises(ConfigError, match="readiness.url"):
        load_config(write(project, MINIMAL + f"\n[readiness]\nurl = {url}\n"))


@pytest.mark.parametrize("field", ["compose_wait_timeout_seconds", "timeout_seconds"])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "true", '"5"'])
def test_config_16_invalid_timeouts(project, field, value):
    with pytest.raises(ConfigError, match=f"readiness.{field} must be a positive finite number"):
        load_config(write(project, MINIMAL + f'\n[readiness]\nurl = "http://localhost:1"\n{field} = {value}\n'))


def test_config_17_timeout_requires_url(project):
    with pytest.raises(ConfigError, match="timeout_seconds requires readiness.url"):
        load_config(write(project, MINIMAL + "\n[readiness]\ntimeout_seconds = 5\n"))


def test_config_18_readiness_url_trailing_slash_is_dropped(project):
    config = load_config(write(project, MINIMAL + '\n[readiness]\nurl = "http://localhost:1/"\n'))
    assert config.readiness.url == "http://localhost:1"


def test_config_19_env_is_read_only(project):
    config = load_config(write(project, FULL))
    with pytest.raises(TypeError):
        config.env["X"] = "y"  # type: ignore[index]


def test_environment_01_exports_exact_contract(project, tmp_path):
    config = load_config(write(project, FULL))
    env = runtime_environment(config, compose_project="tf_sample-api_1", evidence_dir=tmp_path / "ev")
    assert set(env) == set(EXPORTED_KEYS) | {"SAMPLE_PORT"}
    assert env["TESTFORGE_BASE_URL"] == "http://127.0.0.1:18090"
    assert env["TESTFORGE_COMPOSE_PROJECT"] == "tf_sample-api_1"
    assert env["TESTFORGE_COMPOSE_FILE"] == str((project / "compose.yaml").resolve())
    assert env["TESTFORGE_EVIDENCE_DIR"] == str((tmp_path / "ev").resolve())
    assert env["SAMPLE_PORT"] == "18090"


def test_environment_02_base_url_is_empty_without_readiness_url(project, tmp_path):
    env = runtime_environment(load_config(write(project, MINIMAL)), compose_project="tf_x", evidence_dir=tmp_path)
    assert env["TESTFORGE_BASE_URL"] == ""
    assert set(env) == set(EXPORTED_KEYS)


@pytest.mark.parametrize("name", ["", "Tf_x", "tf x", "-x"])
def test_environment_03_rejects_invalid_project_name(project, tmp_path, name):
    with pytest.raises(ValueError, match="Compose project name"):
        runtime_environment(load_config(write(project, MINIMAL)), compose_project=name, evidence_dir=tmp_path)
