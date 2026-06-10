# AGENTS.md

High-signal guidance for agents working in the Pavilion codebase.

## What is Pavilion

Pavilion is a Python 3.6+ testing framework for HPC systems. It uses YAML configs to wrap test codes and run them across different systems via schedulers. The framework is plugin-driven and designed for system validation, acceptance testing, and automated testing scenarios.

## Project Structure

- `bin/pav` — main CLI entry point (bash wrapper that sets PYTHONPATH and python)
- `lib/pavilion/` — core framework code (~140 Python files)
- `lib/` — bundled runtime dependencies (requests, lark, yapsy, etc.) included directly for air-gapped systems
- `test/` — unit tests and test infrastructure
- `examples/` — example test configs and tutorials
- `docs/` — Sphinx documentation
- `builtins/` — built-in configs
- No `setup.py`, `package.json`, or traditional install: runs directly from git clone or extracted tarball

**Key architecture notes:**
- Dependencies are vendored in `lib/sub_repos/` and symlinked to `lib/` (see `lib/sub_repos/README.txt`)
- First run auto-installs dependencies via git clone (from git) or venv + pip (from tarball)
- Plugin system built on yapsy: `lib/pavilion/plugins/` for core, user plugins elsewhere
- Commands live in `lib/pavilion/commands/`

## Developer Commands

### Running Tests

**Primary test runner:**
```bash
./test/run_tests
```

**Focused test execution:**
```bash
./test/run_tests -o 'plugin*'      # Run only tests matching glob pattern
./test/run_tests -s 'spack*'       # Skip tests matching glob
./test/run_tests --re-run          # Only run tests that failed last time
./test/run_tests -v                # Verbose (print logs to stderr)
./test/run_tests -q                # Quiet mode
```

**Test file naming:** Tests must end in `_tests.py` to be discovered.

**CI test categories:**
```bash
./test/run_tests -o style -o debug_prints   # Style checks
./test/run_tests -o 'doc*'                  # Doc tests
./test/run_tests                            # All unit tests
```

**Dependencies for testing:**
```bash
pip install -r test/requirements.txt        # pylint, matplotlib
pip install -r docs/requirements.txt        # sphinx, sphinx_rtd_theme
```

**Spack setup for tests:**
```bash
./test/utils/spack_setup test    # Clones spack v1.0.2, installs patchelf
```

### Running Pavilion

```bash
./bin/pav run <test_name>        # Run a test
./bin/pav status <test_id>       # Check test status
./bin/pav result <test_id>       # View results
./bin/pav build <test_name>      # Build without running
./bin/pav --help                 # Full command list
```

### Documentation

```bash
cd docs
make html                        # Build Sphinx docs → _build/html/
make autodoc                     # Regenerate API docs with sphinx-apidoc
```

Live docs: https://pavilion2.readthedocs.io/en/latest/

## Testing Conventions

**Test base class:** All tests inherit from `pavilion.unittest.PavTestCase` (subclass of `unittest_ex.TestCaseEx`).

**Key testing utilities:**
- `self.pav_cfg` — pre-loaded config for tests, do NOT reload manually
- `self._quick_test(cfg=...)` — creates a simple test instance
- `self._quick_test_cfg()` — returns base test config dict, modify before passing to `_quick_test`
- `self.TEST_DATA_ROOT` — pathlib.Path to `test/data/`
- `self._cmp_files()` — full file content comparison
- `self._cmp_tree()` — compare directory structures
- `self.dbg_print()` — debugging output (caught by style checker)

**Plugin initialization:** If a test uses plugins, call `plugins.initialize_plugins(self.pav_cfg)` in `setUp()` and `plugins._reset_plugins()` in `tearDown()`.

**Test config:** Some tests need `test/data/pav_config_dir/pavilion.yaml` for proxies, no_proxy, etc. (already gitignored).

**Slurm config:** Custom slurm settings go in `test/data/pav_config_dir/modes/local_slurm.yaml`.

**Build before run:** Always call `test.build()` before attempting to run a test instance.

## Python Version Support

**Supported:** 3.6, 3.10, 3.12 (see `.github/py-versions.json`)
**Default:** 3.10 for CI
**Legacy:** 3.6 runs in containers (GitHub Actions doesn't support it natively)

Maintain compatibility with Python 3.6 (no f-strings before 3.6 allowed, no walrus operators, etc.).

## Code Style

**Linter:** pylint 2.13.9 (pinned in `test/requirements.txt`)
**Style tests:** Automatically run via `./test/run_tests -o style`
**No config file:** Pylint runs with defaults; check `test/tests/style_tests.py` for enforcement

**Coverage:** Configured via `.coveragerc`, tracks:
- `lib/pavilion`, `lib/similarity`, `lib/unittest_ex`, `lib/yaml_config`, `lib/yc_yaml`, `lib/hostlist.py`, `test/tests`

## CI Workflow

**Branches:** `develop` (active development), `stable` (releases)
**Workflows:**
- `.github/workflows/unittests.yml` — runs on push/PR to develop/stable
  - Style checks (pylint)
  - Doc tests (sphinx build)
  - Unit tests across Python 3.6, 3.10, 3.12 on ubuntu-latest
  - Uploads `test/output.zip` artifact on failure
- `.github/workflows/coverage.yml` — monthly coverage report (workflow_dispatch)
- `.github/workflows/demo.yml` — demo validation
- `.github/workflows/sync-stable.yml` — syncs stable branch

**CI quirks:**
- Legacy Python (3.6) runs in Docker container: `python:3.6`
- Container needs `/usr/bin/bash` symlink (Pavilion's default shebang)
- `test/output/` has symlink loops; CI zips with `./utils/make_symlinks_relative` before upload
- Spack setup runs before tests: `./test/utils/spack_setup test`

## Common Pitfalls

1. **Don't use `cd` in shell commands.** Pavilion's bash wrapper sets up PYTHONPATH relative to repo root; changing directory breaks it. Use full paths or run from repo root.

2. **Test data goes in `test/data/`.** Prefix with test module name. Plugins for tests only go in `test/data/pav_config_dir/plugins/`.

3. **Don't reload pav_cfg.** Use the provided `self.pav_cfg` from `PavTestCase`. If you need to modify it, use `copy.deepcopy()`.

4. **Plugin initialization is manual.** Tests don't auto-initialize plugins; use `setUp`/`tearDown` if needed.

5. **Dependencies are vendored.** Don't `pip install` Pavilion's runtime deps; they're already in `lib/`. Only install test/doc requirements.

6. **No traditional install.** Don't try to `python setup.py install` or `pip install .`—there's no setup.py. Run directly from the repo.

7. **Test naming matters.** Only files ending in `_tests.py` are discovered by `run_tests`.

## Version and Releases

- `VERSION.txt` is frozen at 2.0 (LANL/DOE approval reasons)
- `RELEASE.txt` tracks actual releases (currently 2.6, moving toward 2.7)
- Git tags denote releases
- ReadTheDocs builds from git submodules (see `.readthedocs.yaml`)

## References

- Main docs: https://pavilion2.readthedocs.io/en/latest/
- Repo: https://github.com/hpc/pavilion2
- Test README: `test/README.md` (detailed testing guide)
- Plugin guide: `lib/pavilion/plugins/README.md`
