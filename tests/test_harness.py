"""Regression tests for bootstrap, validators, hooks, and distribution parity."""

import ast
import compileall
import contextlib
import importlib.util
import io
import json
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import bootstrap

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "template" / ".codex" / "hooks"
PLUGIN_SCRIPTS = ROOT / "plugins" / "python-engineering-harness" / "scripts"
VALUES = {
    "project_name": "test-service",
    "package_name": "test_service",
    "python_version": "3.13",
    "python_image_digest": bootstrap.PYTHON_IMAGE_DIGESTS["3.13"],
    "ruff_target_version": "py313",
    "profile": "service",
    "governance_profile": "none",
}


def load_module(name: str, path: Path) -> ModuleType:
    """Load a repository script as an isolated module."""
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def run_hook(
    script: str, payload: dict[str, Any] | str, cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run one project hook with a serialized Codex payload."""
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        cwd=cwd,
        input=content,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


class BootstrapTests(unittest.TestCase):
    """Validate rendering input and non-destructive merge behavior."""

    def test_supported_python_versions_are_bounded(self) -> None:
        self.assertEqual(bootstrap.normalize_python_version("3.12"), ("3.12", "py312"))
        self.assertEqual(bootstrap.normalize_python_version("3.14"), ("3.14", "py314"))
        for invalid in ("3.11", "3.15", "3.013", "4.0"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bootstrap.normalize_python_version(invalid)

    def test_supported_python_images_are_pinned_by_digest(self) -> None:
        self.assertEqual(
            set(bootstrap.PYTHON_IMAGE_DIGESTS),
            {f"3.{minor}" for minor in bootstrap.SUPPORTED_PYTHON_MINORS},
        )
        for digest in bootstrap.PYTHON_IMAGE_DIGESTS.values():
            self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")

    def test_python_keyword_is_not_a_package_name(self) -> None:
        with self.assertRaises(ValueError):
            bootstrap.validate_package_name("class")

    def test_project_name_cannot_break_rendered_configuration(self) -> None:
        for invalid in ("", ".hidden", "bad name", 'bad"name', "line\nbreak"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bootstrap.validate_project_name(invalid)

    def test_merge_never_overwrites_an_existing_conflict_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            target = root / "target"
            template.mkdir()
            target.mkdir()
            (template / "config.txt").write_text("new", encoding="utf-8")
            (target / "config.txt").write_text("old", encoding="utf-8")
            existing = target / "config.txt.harness-new"
            existing.write_text("keep", encoding="utf-8")

            conflicts = bootstrap.copy_template(template, target, VALUES, merge=True)

            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
            self.assertEqual(conflicts, [target / "config.txt.harness-new.2"])
            self.assertEqual(conflicts[0].read_text(encoding="utf-8"), "new")

    def test_merge_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            target = root / "target"
            outside = root / "outside"
            (template / "nested").mkdir(parents=True)
            (template / "nested" / "file.txt").write_text("data", encoding="utf-8")
            target.mkdir()
            outside.mkdir()
            (target / "nested").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ValueError):
                bootstrap.copy_template(template, target, VALUES, merge=True)
            self.assertFalse((outside / "file.txt").exists())

    def test_render_preserves_template_file_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template"
            target = root / "target"
            template.mkdir()
            target.mkdir()
            executable = template / "executable.py"
            regular = template / "regular.py"
            executable.write_text("print('ok')\n", encoding="utf-8")
            regular.write_text("VALUE = 1\n", encoding="utf-8")
            executable.chmod(0o755)
            regular.chmod(0o644)

            bootstrap.copy_template(template, target, VALUES, merge=False)

            self.assertEqual(stat.S_IMODE((target / executable.name).stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((target / regular.name).stat().st_mode), 0o644)

    def test_complete_template_renders_token_clean_and_compiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rendered"
            target.mkdir()
            bootstrap.copy_template(ROOT / "template", target, VALUES, merge=False)
            unresolved = [
                path
                for path in target.rglob("*")
                if path.is_file()
                and b"{{" in path.read_bytes()
                and not path.name.endswith((".png", ".jpg"))
            ]
            self.assertEqual(unresolved, [])
            with (target / "pyproject.toml").open("rb") as handle:
                self.assertIsInstance(tomllib.load(handle), dict)
            self.assertTrue(compileall.compile_dir(target, quiet=1))

    def test_profiles_keep_service_default_and_avoid_artificial_workspace_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for profile in bootstrap.PROFILES:
                with self.subTest(profile=profile):
                    target = root / profile
                    result = bootstrap.main(
                        [
                            "--name",
                            f"sample-{profile}",
                            "--package",
                            f"sample_{profile}",
                            "--target",
                            str(target),
                            "--profile",
                            profile,
                        ]
                    )
                    self.assertEqual(result, 0)
                    manifest = json.loads((target / ".harness.json").read_text(encoding="utf-8"))
                    self.assertEqual(manifest["version"], bootstrap.HARNESS_VERSION)
                    self.assertEqual(manifest["profile"], profile)
                    self.assertEqual(manifest["governanceProfile"], "none")
                    self.assertEqual(manifest["governanceOverlays"], [])
                    self.assertIn("files", manifest)
                    self.assertTrue((target / "scripts" / "quality_gate.py").is_file())
                    self.assertFalse((target / "governance").exists())
                    self.assertTrue(compileall.compile_dir(target, quiet=1))

            service = root / "service"
            self.assertTrue((service / "Dockerfile").is_file())
            self.assertIn("structlog", (service / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertIn(
                "opentelemetry-sdk",
                (service / "pyproject.toml").read_text(encoding="utf-8"),
            )
            self.assertTrue((service / "tests/unit/test_observability.py").is_file())
            self.assertIn(
                "--extra observability",
                (service / ".github/workflows/quality.yml").read_text(encoding="utf-8"),
            )

            library = root / "library"
            self.assertFalse((library / "Dockerfile").exists())
            library_project = (library / "pyproject.toml").read_text(encoding="utf-8")
            self.assertNotIn("pydantic", library_project)
            self.assertNotIn("structlog", library_project)
            self.assertNotIn("langfuse", library_project)
            self.assertNotIn("opentelemetry", library_project)
            self.assertFalse((library / "tests/unit/test_observability.py").exists())
            library_workflow = (library / ".github/workflows/quality.yml").read_text(
                encoding="utf-8"
            )
            self.assertIn("uv sync --frozen --all-groups", library_workflow)
            self.assertNotIn("observability", library_workflow)
            library_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in library.rglob("*")
                if path.is_file() and path.suffix in {".json", ".md", ".toml", ".yml"}
            ).lower()
            self.assertNotIn("langfuse", library_text)
            self.assertNotIn("mypy src tests", library_text)
            self.assertNotIn("bandit -c pyproject.toml -r src", library_text)

            workspace = root / "workspace"
            self.assertFalse((workspace / "Dockerfile").exists())
            self.assertFalse((workspace / "src").exists())
            self.assertFalse((workspace / "tests").exists())
            with (workspace / "pyproject.toml").open("rb") as handle:
                project = tomllib.load(handle)
            self.assertFalse(project["tool"]["uv"]["package"])
            self.assertNotIn("build-system", project)
            workspace_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in workspace.rglob("*")
                if path.is_file() and path.suffix in {".json", ".md", ".toml", ".yml"}
            ).lower()
            self.assertNotIn("langfuse", workspace_text)
            self.assertNotIn("mypy src tests", workspace_text)
            workspace_workflow = (workspace / ".github/workflows/quality.yml").read_text(
                encoding="utf-8"
            )
            self.assertIn("uv sync --frozen --all-packages --all-groups", workspace_workflow)
            self.assertNotIn("observability", workspace_workflow)

            for profile in ("service", "library", "workspace"):
                governed = root / f"{profile}-agentic"
                self.assertEqual(
                    bootstrap.main(
                        [
                            "--name",
                            f"sample-{profile}-agentic",
                            "--package",
                            f"sample_{profile}_agentic",
                            "--target",
                            str(governed),
                            "--profile",
                            profile,
                            "--governance-profile",
                            "agentic",
                        ]
                    ),
                    0,
                )
                catalog = json.loads(
                    (governed / "governance/control-catalog.json").read_text(encoding="utf-8")
                )
                observability = next(
                    control for control in catalog["controls"] if control["id"] == "CPH-OBS-001"
                )
                checks = observability["assurance"]["checks"]
                if profile == "service":
                    self.assertIn("tests/unit/test_observability.py", checks)
                    self.assertIn("tests/unit/test_logging.py", checks)
                else:
                    self.assertNotIn("tests/unit/test_observability.py", checks)
                    self.assertNotIn("tests/unit/test_logging.py", checks)

    def test_governance_profiles_and_overlays_render_versioned_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for governance_profile in bootstrap.GOVERNANCE_PROFILES[1:]:
                with self.subTest(governance_profile=governance_profile):
                    target = root / governance_profile
                    arguments = [
                        "--name",
                        f"sample-{governance_profile}",
                        "--package",
                        f"sample_{governance_profile.replace('-', '_')}",
                        "--target",
                        str(target),
                        "--governance-profile",
                        governance_profile,
                    ]
                    if governance_profile == "agentic":
                        arguments.extend(
                            [
                                "--governance-overlay",
                                "dora",
                                "--governance-overlay",
                                "iso-iec-42001",
                            ]
                        )
                    self.assertEqual(bootstrap.main(arguments), 0)
                    manifest = json.loads((target / ".harness.json").read_text(encoding="utf-8"))
                    selection = json.loads(
                        (target / "governance/governance-profile.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(manifest["governanceProfile"], governance_profile)
                    self.assertEqual(
                        manifest["governanceCatalogVersion"],
                        bootstrap.GOVERNANCE_CATALOG_VERSION,
                    )
                    self.assertEqual(selection["name"], governance_profile)
                    required = selection["required_controls"]
                    self.assertEqual(len(required), len(set(required)))
                    self.assertTrue((target / "governance/control-catalog.json").is_file())
                    self.assertEqual(bootstrap.check_target(target), [])

            agentic = json.loads(
                (root / "agentic/governance/governance-profile.json").read_text(encoding="utf-8")
            )
            self.assertEqual(agentic["overlays"], ["dora", "iso-iec-42001"])
            self.assertEqual(agentic["framework_versions"]["dora"], "eu-2022-2554")
            self.assertIn("CPH-RES-001", agentic["required_controls"])

    def test_governance_overlay_requires_enabled_unique_profile(self) -> None:
        with self.assertRaises(SystemExit):
            bootstrap.parse_args(
                [
                    "--name",
                    "test",
                    "--package",
                    "test",
                    "--target",
                    "target",
                    "--governance-overlay",
                    "dora",
                ]
            )
        with self.assertRaises(SystemExit):
            bootstrap.parse_args(
                [
                    "--name",
                    "test",
                    "--package",
                    "test",
                    "--target",
                    "target",
                    "--governance-profile",
                    "baseline",
                    "--governance-overlay",
                    "dora",
                    "--governance-overlay",
                    "dora",
                ]
            )

    def test_git_init_uses_main_and_matches_generated_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            result = bootstrap.main(
                [
                    "--name",
                    "branch-test",
                    "--package",
                    "branch_test",
                    "--target",
                    str(target),
                    "--git-init",
                ]
            )
            self.assertEqual(result, 0)
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(branch, "main")
            self.assertIn(
                branch, bootstrap._workflow_branches(target / ".github/workflows/quality.yml")
            )
            self.assertEqual(bootstrap.check_target(target), [])

    def test_dry_run_does_not_create_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = bootstrap.main(
                    [
                        "--name",
                        "dry-run",
                        "--package",
                        "dry_run",
                        "--target",
                        str(target),
                        "--dry-run",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertFalse(target.exists())
            self.assertIn("NEW", output.getvalue())

    def test_dry_run_inspects_nonempty_target_without_merge_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            (target / "README.md").write_text("custom", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = bootstrap.main(
                    [
                        "--name",
                        "dry-run",
                        "--package",
                        "dry_run",
                        "--target",
                        str(target),
                        "--dry-run",
                    ]
                )
            self.assertEqual(result, 1)
            self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "custom")
            self.assertFalse((target / ".harness.json").exists())
            self.assertIn("CONFLICT README.md", output.getvalue())

    def test_manifest_hash_allows_safe_update_but_preserves_customization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            destination = target / "config.txt"
            destination.write_text("old", encoding="utf-8")
            previous = {"config.txt": {"sha256": bootstrap.sha256(b"old"), "mode": "0644"}}
            rendered = {Path("config.txt"): bootstrap.RenderedFile(b"new", 0o644)}

            changes = bootstrap.plan_changes(rendered, target, previous)
            self.assertEqual(changes[0].status, "update")
            bootstrap.apply_changes(changes, target, merge=True)
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")

            destination.write_text("custom", encoding="utf-8")
            changes = bootstrap.plan_changes(rendered, target, previous)
            self.assertEqual(changes[0].status, "conflict")
            conflicts = bootstrap.apply_changes(changes, target, merge=True)
            self.assertEqual(destination.read_text(encoding="utf-8"), "custom")
            self.assertEqual(conflicts[0].read_text(encoding="utf-8"), "new")

    def test_check_detects_permission_drift_and_pending_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            self.assertEqual(
                bootstrap.main(
                    [
                        "--name",
                        "check-test",
                        "--package",
                        "check_test",
                        "--target",
                        str(target),
                    ]
                ),
                0,
            )
            gate = target / "scripts" / "quality_gate.py"
            gate.chmod(0o600)
            (target / "README.md.harness-new").write_text("pending", encoding="utf-8")
            errors = bootstrap.check_target(target)
            self.assertTrue(any("permission drift" in error for error in errors))
            self.assertTrue(any("pending conflict" in error for error in errors))

    def test_check_detects_version_tokens_ci_and_missing_documented_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            self.assertEqual(
                bootstrap.main(
                    [
                        "--name",
                        "audit-test",
                        "--package",
                        "audit_test",
                        "--target",
                        str(target),
                    ]
                ),
                0,
            )
            manifest_path = target / ".harness.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = "0.4.0"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (target / "unrendered.txt").write_text("{{PROJECT_NAME}}", encoding="utf-8")
            workflow = target / ".github/workflows/quality.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace("branches: [main]", "branches: [dev]"),
                encoding="utf-8",
            )
            with (target / "AGENTS.md").open("a", encoding="utf-8") as handle:
                handle.write("\n`uv run python scripts/missing.py`\n")

            errors = bootstrap.check_target(target)
            self.assertTrue(any("harness version" in error for error in errors))
            self.assertTrue(any("unrendered token" in error for error in errors))
            self.assertTrue(any("CI branch mismatch" in error for error in errors))
            self.assertTrue(any("missing file" in error for error in errors))


class ValidatorTests(unittest.TestCase):
    """Exercise architecture and MCP policy regressions."""

    architecture: ModuleType
    governance: ModuleType
    mcp: ModuleType
    quality: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.architecture = load_module(
            "harness_validate_architecture",
            ROOT / "template" / "scripts" / "validate_architecture.py",
        )
        cls.mcp = load_module(
            "harness_validate_mcp", ROOT / "template" / "scripts" / "validate_mcp_config.py"
        )
        cls.quality = load_module(
            "harness_quality_gate", ROOT / "template" / "scripts" / "quality_gate.py"
        )
        cls.governance = load_module(
            "harness_governance_gate", ROOT / "template" / "scripts" / "governance_gate.py"
        )

    def test_architecture_resolves_from_import_aliases(self) -> None:
        tree = ast.parse("from package import adapters\nfrom .. import entrypoints\n")
        imports = self.architecture.imported_modules(tree, ("package", "domain", "model"))
        self.assertEqual(imports, [(1, "package.adapters"), (2, "package.entrypoints")])

    def test_architecture_layer_ignores_package_name(self) -> None:
        self.assertEqual(self.architecture.layer_for(Path("domain/adapters/client.py")), "adapters")

    def test_architecture_blocks_from_import_of_outer_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / "src"
            path = src / "package" / "domain" / "model.py"
            path.parent.mkdir(parents=True)
            path.write_text("from package import adapters\n", encoding="utf-8")
            violations = self.architecture.validate_file(path, src)
            self.assertEqual(len(violations), 1)
            self.assertIn("adapters", violations[0].message)

    def test_architecture_default_deny_boundary_reports_module_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "packages" / "core" / "src" / "core"
            package.mkdir(parents=True)
            path = package / "model.py"
            path.write_text(
                "import json\nimport requests\nimport importlib\nimportlib.import_module('x')\n",
                encoding="utf-8",
            )
            boundary = self.architecture.Boundary(package, ("stdlib", "core"), True)
            violations = self.architecture.validate_boundary_file(path, root, boundary)
            self.assertEqual([item.line for item in violations], [2, 4])
            self.assertTrue(all("core.model" in item.message for item in violations))

    def test_architecture_discovers_multiple_source_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one", "two"):
                (root / "services" / name / "src").mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                "[tool.engineering-harness.architecture]\n"
                'source-roots = ["services/*/src"]\n'
                "clean-architecture = false\n",
                encoding="utf-8",
            )
            roots, clean, boundaries = self.architecture.load_config(root)
            self.assertEqual(len(roots), 2)
            self.assertFalse(clean)
            self.assertEqual(boundaries, [])

    def test_quality_gate_keeps_named_checks_for_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "[tool.engineering-harness.quality]\n"
                'source-roots = ["packages/*/src"]\n'
                'test-roots = ["packages/*/tests"]\n',
                encoding="utf-8",
            )
            checks = {check.name: check.command for check in self.quality.configured_checks(root)}
            self.assertIn("governance", checks)
            self.assertIn("typing", checks)
            self.assertIn("security", checks)
            self.assertEqual(checks["typing"], ())
            self.assertEqual(checks["security"], ())

    def test_governance_source_catalog_is_valid(self) -> None:
        report, errors = self.governance.run_source(ROOT, None)
        self.assertEqual(errors, [])
        self.assertEqual(report["status"], "pass")
        self.assertGreater(report["control_count"], 0)

    def test_governance_gate_rejects_untreated_high_risk_and_expired_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            self.assertEqual(
                bootstrap.main(
                    [
                        "--name",
                        "governed-service",
                        "--package",
                        "governed_service",
                        "--target",
                        str(target),
                        "--governance-profile",
                        "agentic",
                    ]
                ),
                0,
            )
            risk_path = target / "governance/risks/risk-register.json"
            risk_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "risks": [{"id": "RISK-001", "owner": "service-owner", "severity": "high"}],
                    }
                ),
                encoding="utf-8",
            )
            exception_path = target / "governance/exceptions.json"
            exception_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "exceptions": [
                            {
                                "expires_on": "2000-01-01",
                                "id": "EXC-001",
                                "owner": "service-owner",
                                "status": "approved",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report, errors = self.governance.run_generated(target, None)
            self.assertEqual(report["status"], "fail")
            self.assertTrue(any("formal decision" in error for error in errors))
            self.assertTrue(any("expired" in error for error in errors))

    def test_mcp_rejects_unpinned_runner_and_literal_secret_argument(self) -> None:
        config = {
            "command": "npx",
            "args": ["-y", "company-mcp@latest", "--token", "plain-secret"],
            "startup_timeout_sec": 10,
            "tool_timeout_sec": 60,
        }
        errors = self.mcp.validate_server(Path(".codex/config.toml"), "company", config)
        self.assertTrue(any("exact @version" in item for item in errors))
        self.assertTrue(any("sensitive argument" in item for item in errors))

    def test_mcp_rejects_unpinned_direct_uvx_package(self) -> None:
        config = {
            "command": "uvx",
            "args": ["company-mcp"],
            "startup_timeout_sec": 10,
            "tool_timeout_sec": 60,
        }
        errors = self.mcp.validate_server(Path(".codex/config.toml"), "company", config)
        self.assertTrue(any("exact == version" in item for item in errors))

    def test_mcp_rejects_url_credentials_and_mixed_sensitive_header(self) -> None:
        config = {
            "url": "https://user:password@example.com/mcp",
            "http_headers": {"Authorization": "hardcoded-token"},
            "tool_timeout_sec": 60,
        }
        errors = self.mcp.validate_server(Path(".codex/config.toml"), "company", config)
        self.assertTrue(any("user information" in item for item in errors))
        self.assertTrue(any("env_http_headers" in item for item in errors))


class HookTests(unittest.TestCase):
    """Verify fail-closed behavior and mutation classification."""

    def test_pre_tool_hook_fails_closed_on_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_hook("guard_mcp.py", "{", Path(directory))
        self.assertEqual(result.returncode, 2)
        self.assertIn("failed closed", result.stderr)

    def test_camel_case_mutation_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "mcp__issues__createIssue",
                "tool_input": {"title": "test"},
            }
            result = run_hook("guard_mcp.py", payload, Path(directory))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")

    def test_production_mutation_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "mcp__issues__create_issue",
                "tool_input": {"environment": "production"},
            }
            result = run_hook("guard_mcp.py", payload, Path(directory))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_bash_blocks_sensitive_path_for_arbitrary_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "Bash",
                "tool_input": {"command": "python3 -c 'open(\".env\").read()'"},
            }
            result = run_hook("validate_bash.py", payload, Path(directory))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_bash_allows_environment_example(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "Bash",
                "tool_input": {"command": "cat .env.example"},
            }
            result = run_hook("validate_bash.py", payload, Path(directory))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_bash_allows_jq_environment_property_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "Bash",
                "tool_input": {"command": "jq -r '.env // {} | keys' ~/.codex/config.toml"},
            }
            result = run_hook("validate_bash.py", payload, Path(directory))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_bash_blocks_environment_file_used_as_jq_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "cwd": directory,
                "tool_name": "Bash",
                "tool_input": {"command": "jq -r '.' .env"},
            }
            result = run_hook("validate_bash.py", payload, Path(directory))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_stop_scan_finds_secret_written_outside_edit_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            fake_key = "AKIA" + "1234567890ABCDEF"
            (root / "generated.txt").write_text(fake_key + "\n", encoding="utf-8")
            payload = {"cwd": directory, "tool_name": "Stop", "tool_input": {}}
            result = run_hook("scan_worktree.py", payload, root)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("generated.txt", decision["reason"])

    def test_stop_scan_is_a_no_op_outside_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {"cwd": directory, "tool_name": "Stop", "tool_input": {}}
            result = run_hook("scan_worktree.py", payload, root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class DistributionTests(unittest.TestCase):
    """Keep duplicated security code and machine-readable files valid."""

    def test_repository_quality_gate_is_enforced_in_ci(self) -> None:
        """Keep the complete local gate represented in the required workflow."""
        workflow = (ROOT / ".github/workflows/harness-quality.yml").read_text(encoding="utf-8")
        self.assertIn("repository-quality:", workflow)
        self.assertIn("uv sync --frozen --all-groups", workflow)
        self.assertIn("uv run python scripts/quality_gate.py", workflow)

    def test_distributed_actions_and_container_images_are_immutable(self) -> None:
        """Require immutable references in repository-owned distributed automation."""
        workflows = (
            ROOT / ".github/workflows/harness-quality.yml",
            ROOT / "template/.github/workflows/quality.yml",
            ROOT / "profiles/library/.github/workflows/quality.yml",
            ROOT / "profiles/workspace/.github/workflows/quality.yml",
        )
        mutable_action = re.compile(r"uses:\s+[^\s@]+@v\d+\s*$", re.MULTILINE)
        for workflow in workflows:
            with self.subTest(workflow=workflow):
                self.assertIsNone(mutable_action.search(workflow.read_text(encoding="utf-8")))

        dockerfile = (ROOT / "template/Dockerfile").read_text(encoding="utf-8")
        self.assertEqual(
            dockerfile.count("python:{{PYTHON_VERSION}}-slim@{{PYTHON_IMAGE_DIGEST}}"), 2
        )
        self.assertRegex(dockerfile, r"ghcr\.io/astral-sh/uv:[^\s@]+@sha256:[0-9a-f]{64}")

    def test_public_maintenance_contract_is_documented(self) -> None:
        """Keep security, upgrades, and independent artifact versions discoverable."""
        required = (
            "SECURITY.md",
            "CHANGELOG.md",
            "docs/UPGRADING.md",
            "docs/VERSIONING.md",
            ".github/dependabot.yml",
        )
        for relative in required:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("not a sandbox", security)
        versioning = (ROOT / "docs/VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("independently versioned artifacts", versioning)

    def test_service_matrix_installs_observability_extra(self) -> None:
        """Keep service-only dependencies available to the generated-profile gate."""
        workflow = (ROOT / ".github/workflows/harness-quality.yml").read_text(encoding="utf-8")
        self.assertIn("if: matrix.profile == 'service'", workflow)
        self.assertIn(
            "uv sync --frozen --all-packages --all-groups --extra observability",
            workflow,
        )
        self.assertIn("if: matrix.profile != 'service'", workflow)

    def test_governance_json_documents_parse(self) -> None:
        paths = [
            *sorted((ROOT / "governance").rglob("*.json")),
            *sorted((ROOT / "template/governance").rglob("*.json")),
        ]
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_template_and_plugin_security_scripts_match(self) -> None:
        names = {path.name for path in HOOKS.glob("*.py")}
        self.assertEqual(names, {path.name for path in PLUGIN_SCRIPTS.glob("*.py")})
        for name in names:
            with self.subTest(name=name):
                self.assertEqual((HOOKS / name).read_bytes(), (PLUGIN_SCRIPTS / name).read_bytes())

    def test_json_manifests_and_hooks_parse(self) -> None:
        paths = (
            ROOT / ".agents" / "plugins" / "marketplace.json",
            ROOT / "plugins" / "python-engineering-harness" / ".codex-plugin" / "plugin.json",
            ROOT / "plugins" / "python-engineering-harness" / "hooks" / "hooks.json",
            ROOT / "template" / ".codex" / "hooks.json",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_plugin_and_marketplace_names_and_paths_match(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
        )
        plugin = json.loads(
            (ROOT / "plugins/python-engineering-harness/.codex-plugin/plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(marketplace["plugins"][0]["name"], plugin["name"])
        self.assertEqual(
            marketplace["plugins"][0]["source"]["path"],
            "./plugins/python-engineering-harness",
        )

    def test_quality_plugin_prefers_project_runner_without_layout_assumption(self) -> None:
        paths = (
            ROOT / "plugins/python-engineering-harness/skills/quality-gate/SKILL.md",
            ROOT / "template/.agents/skills/quality-gate/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("scripts/quality_gate.py", content)
                self.assertNotIn("mypy src tests", content)
                self.assertNotIn("bandit -c pyproject.toml -r src", content)

    def test_project_config_uses_separate_hooks_file(self) -> None:
        with (ROOT / "template/.codex/config.toml").open("rb") as handle:
            config = tomllib.load(handle)
        self.assertTrue(config["features"]["hooks"])
        self.assertNotIn("hooks", config)

    def test_plugin_hooks_resolve_scripts_through_plugin_root(self) -> None:
        content = (ROOT / "plugins/python-engineering-harness/hooks/hooks.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("$PLUGIN_ROOT/scripts/", content)
        self.assertNotIn("$(git rev-parse", content)

    def test_postponed_annotations_import_is_not_distributed(self) -> None:
        forbidden = "from __future__ import " + "annotations"
        offenders = [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*.py")
            if ".venv" not in path.parts
            if forbidden in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])
        guidance = (ROOT / "template/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"Do not use `{forbidden}`", guidance)

    def test_no_legacy_tool_references_are_distributed(self) -> None:
        legacy_name = bytes((99, 108, 97, 117, 100, 101)).decode()
        forbidden_parts = (
            "." + legacy_name,
            legacy_name.upper() + "_",
            legacy_name.title() + " Code",
        )
        offenders: list[Path] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(value in content for value in forbidden_parts):
                offenders.append(path.relative_to(ROOT))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
