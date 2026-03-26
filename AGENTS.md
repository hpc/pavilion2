# AGENTS.md – Guidance for Automated Coding Agents

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Build Commands](#build-commands)
3. [Linting & Static Analysis](#linting--static-analysis)
4. [Testing](#testing)
   - [Run All Tests](#run-all-tests)
   - [Run a Single Test](#run-a-single-test)
   - [Re‑run Failed Tests](#re‑run-failed-tests)
   - [Test Configuration File](#test‑configuration‑file)
5. [Documentation Build](#documentation-build)
6. [Code Style Guidelines](#code-style-guidelines)
   - [Imports](#imports)
   - [Formatting & Line Length](#formatting--line-length)
   - [Type Annotations](#type-annotations)
   - [Naming Conventions](#naming-conventions)
   - [Error Handling & Logging](#error-handling--logging)
   - [Docstrings & Sphinx Compatibility](#docstrings--sphinx-compatibility)
   - [Module Structure & Independence](#module-structure--independence)
7. [Contributor Checklist](#contributor-checklist)
8. [Cursor / Copilot Rules](#cursor--copilot-rules)
9. [Continuous Integration (CI) Details](#continuous-integration-ci-details)
10. [References & Helpful Links](#references--helpful-links)

---

## Project Overview

* **Name**: *Pavilion* – a flexible, extensible framework for defining and running HPC tests.
* **Primary Language**: Python 3.6+ (the code imports `pavilion` modules directly from `lib/`).
* **Entry Point**: `bin/pav` (a thin Bash wrapper that invokes `python -m pavilion.main`).
* **Key Packages** (vendored under `lib/`):
  * `pavilion` – core implementation.
  * `yc_yaml`, `yaml_config` – YAML handling utilities.
  * Third‑party sub‑repos (urllib3, requests, etc.) are vendored for reproducible builds.

---

## Build Commands

The project does not require a compiled build step, but the following commands are commonly used by agents:

* **Install development dependencies** (executed from the repository root):
  ```bash
  # Virtual‑env recommended
  python3 -m venv .env && source .env/bin/activate
  pip install -U pip
  pip install -r test/requirements.txt   # pylint, matplotlib
  pip install -r docs/requirements.txt   # sphinx, theme
  ```
* **Refresh vendored sub‑repos** (if they have been removed):
  ```bash
  git submodule update --init --recursive
  ```
* **Package the library** (useful for downstream CI):
  ```bash
  # No `setup.py` at the top level – the library lives in lib/
  # To create a source distribution:
  python -m pip install build
  python -m build lib/pavilion
  ```

---

## Linting & Static Analysis

The repository uses **pylint** (pinned to `2.13.9`).  Run it against the library source:

```bash
pylint lib/pavilion
```

Typical configuration files (`.pylintrc`) are vendored inside the urllib3 sub‑repo, but the project follows the default pylint behaviour with a handful of custom disables:

* `broad-except` – allowed in `main.py` where a top‑level catch logs and exits.
* `invalid-name` – snake_case is enforced for variables & functions; PascalCase for classes.

Agents should treat any pylint warnings as *fixable* unless they are explicitly disabled.

---

## Testing

All unit tests live under `test/tests/` and follow the naming convention `*_tests.py`.  The test runner lives at `test/run_tests`.

### Run All Tests

```bash
./test/run_tests            # discovers and runs every *_tests.py file
```

The script automatically:
* Clears the `test/working_dir` unless `-C/--no-clear` is passed.
* Sets up the `PYTHONPATH` to include `lib/`.
* Generates a temporary file with failed test names for later re‑run.

### Run a Single Test

The runner supports **`--only`** (`-o`) which accepts glob patterns matching the *suite* and *test* name without the `test_` prefix.  Example:

```bash
# Run only the `test_build` method in the BuildCmdTests suite
./test/run_tests -o 'BuildCmdTests.test_build'

# Run any test whose name contains "scheduler"
./test/run_tests -o '*scheduler*'
```

The pattern is applied after stripping the leading `test_` from each method name, so you can omit it for brevity:

```bash
./test/run_tests -o 'build'          # matches BuildCmdTests.test_build
```

### Re‑run Failed Tests

After a test run, failures are written to a temporary file (`/tmp/.pavilion_run_test_failures_<user>.txt`).  Re‑run only those failures with:

```bash
./test/run_tests --re-run
```

### Test Configuration File

The test suite expects a minimal configuration file at:

```
test/data/pav_config_dir/pavilion.yaml
```

If missing, the runner prints an error.  A simple placeholder can be created with:

```bash
ln -s pavilion.yaml.ci test/data/pav_config_dir/pavilion.yaml
# Append required keys (e.g., working_dir, spack_path) – see CI scripts for details.
```

---

## Documentation Build

Documentation sources are under `docs/`.  A minimal Makefile is provided:

```bash
cd docs
make html          # builds HTML documentation in docs/_build/html
make clean          # removes the build directory
make autodoc        # regenerates API docs from lib/pavilion/*
```

The tasks require the packages listed in `docs/requirements.txt` (Sphinx ≥ 4.0, theme ≥ 1.0).

---

## Code Style Guidelines

> The **DevelopmentGuidelines.rst** file already states the high‑level expectations.  The sections below expand on those points for automated agents.

### Imports

* **Standard library imports** first, sorted alphabetically.
* **Third‑party imports** second (e.g., `import yaml`), then **internal imports** last.
* Use absolute imports when referencing modules inside `lib/` – e.g., `from pavilion import config`.
* Avoid wildcard imports (`from module import *`).
* Group imports with a single blank line between sections.

### Formatting & Line Length

* Follow **PEP 8** – maximum line length **80 characters**.
* Use **4 spaces** for indentation (no tabs).
* Trailing whitespace is prohibited.
* End files with a single newline.
* Wrap long import statements with parentheses or the backslash continuation style endorsed by Pylint.

### Type Annotations

* All public functions, methods, and class constructors **must** have type hints for parameters and return values.
* Use `from typing import *` only when necessary; prefer concrete types (`str`, `int`, `Path`, `Mapping[str, Any]`).
* For `*args`/`**kwargs` annotate as `*args: Any, **kwargs: Any` if the exact type is not known.
* Return `None` explicitly when a function does not return a value.

### Naming Conventions

| Entity | Recommended Style |
|--------|-------------------|
| Packages / Modules | **snake_case** (e.g., `pavilion`, `yc_yaml`) |
| Classes | **PascalCase** (e.g., `PavTestCase`, `CommandResult`) |
| Functions / Methods | **snake_case** (e.g., `run_cmd`, `get_parser`) |
| Constants | **UPPER_SNAKE_CASE** (e.g., `MIN_SUPPORTED_MINOR_VERSION`) |
| Private helpers | prefix with a single underscore (`_private`) |
| Test classes | end with `Tests` (e.g., `BuildCmdTests`) |
| Test methods | start with `test_` followed by descriptive name |

### Error Handling & Logging

* Use **exception hierarchy** defined in `pavilion.errors`.  Raise custom exceptions rather than generic `Exception` where appropriate.
* All top‑level command entry points (`pavilion.main`, `pavilion.commands.*`) should catch `Exception` only to log via the **`output`** module and exit with a non‑zero status.
* Prefer **`logging`** (module‑level loggers) for internal diagnostics; the `output` helper is reserved for user‑facing messages.
* When catching specific exceptions, re‑raise them after adding context if the caller cannot recover.
* Do not swallow exceptions silently unless the situation is truly ignorable and documented.

### Docstrings & Sphinx Compatibility

* Use **reST / Sphinx** style docstrings for all public objects.
* Include **`:param <name>: <description>`** and **`:type <name>: <type>`** for each parameter.
* Document return values with **`:return: <description>`** and **`:rtype: <type>`**.
* One‑line summary should fit on a single line; a blank line separates the summary from the extended description.
* Example:
  ```python
  def foo(bar: int) -> str:
      """Return a string representation of ``bar``.

      :param bar: integer to convert
      :type bar: int
      :return: string version of ``bar``
      :rtype: str
      """
      return str(bar)
  ```

### Module Structure & Independence

* Each top‑level module in `lib/pavilion` should be **self‑contained** – import other internal modules **lazily** when possible to avoid circular imports.
* Keep public APIs small; expose functionality through `__all__` where relevant.
* Helper utilities that are not part of the public API belong in a private submodule (e.g., `._utils`).
* Avoid heavy side‑effects at import time – only configure logging or parse CLI arguments in `if __name__ == '__main__':` blocks or dedicated entry points.

---

## Contributor Checklist

1. **Run the full test suite**: `./test/run_tests` – ensure **0 failures**.
2. **Run pylint**: `pylint lib/pavilion` – fix all new warnings.
3. **Check formatting**: verify line length ≤ 80, no trailing whitespace.
4. **Update documentation** (if new public API added): run `make autodoc` inside `docs/` and commit generated files if they change.
5. **Add type hints** for any newly introduced functions.
6. **Write a docstring** for every public class/function.
7. **Commit with a clear message** – "Add <feature>: short rationale".

---

## Cursor / Copilot Rules

The repository does **not** contain a `.cursor/` directory or a `.github/copilot-instructions.md` file.  Therefore there are no special cursor or Copilot directives to obey.  Agents should follow the generic style rules described above.

---

## Continuous Integration (CI) Details

* **GitHub Actions** workflows** are defined in `.github/workflows/`:
  * `unittests.yml` runs the test suite across multiple Python versions (3.7, 3.9, 3.10, 3.12).
  * `style` job runs pylint with the `-q -o style -o debug_prints` flags.
  * `docs` job builds the Sphinx documentation.
* The CI scripts mirror the local commands described earlier (install dependencies, link configuration, run `./test/run_tests`).
* Agents should keep CI compatibility in mind – avoid adding dependencies that are not listed in `test/requirements.txt` or `docs/requirements.txt` unless they are also added to the appropriate CI setup.

---

## References & Helpful Links

* **PEP 8 – Style Guide**: https://peps.python.org/pep-0008/
* **Sphinx Documentation**: https://www.sphinx-doc.org/
* **pylint User Guide**: https://pylint.pycqa.org/
* **Python Type Hinting**: https://docs.python.org/3/library/typing.html
* **Project’s Development Guidelines**: `docs/DevelopmentGuidelines.rst`

---

*This file is intended for consumption by AI‑assisted coding agents and human contributors alike.  Keep it up‑to‑date as the project evolves.*
