# Configuration Management

This document defines how the AFRM application is placed under configuration control: what is controlled, how the baseline is identified, and how changes are proposed, made, verified and released.

## 1. Configuration items

| Item | Location | Description |
|---|---|---|
| Source code | `src/afrm/` | Application modules |
| Configuration data | `config/afrm_config.json` | Aircraft, route, reserve policy, monitoring limits, scenarios, noise model |
| Tests | `tests/` | Automated test suite |
| Build and tool configuration | `pyproject.toml`, `.python-version`, `requirements-dev.txt`, `requirements-bench.txt` | Interpreter, dependencies, lint, type-check, test and coverage settings |
| CI and dependency monitoring | `.github/workflows/ci.yml`, `.github/dependabot.yml` | Automated verification and update checks |
| Benchmark | `bench/benchmark.py` | Performance measurement |
| Documentation | `README.md`, `CHANGELOG.md`, `docs/` | Requirements, test plan, change requests, reviews |
| Results | `results/` | Recorded test, benchmark and scenario outputs |

## 2. Baseline identification

| Field | Value |
|---|---|
| Baseline | **v1.0.0** (Assignment 1 release) |
| Tag | `v1.0.0` |
| Commit | `755a087b391bb9a10463451c0a663ca60351cf9d` |
| Date | 22 October 2026, 20:52 (UTC+1) |
| Release | GitHub release "v1.0.0 – AFRM prototype" |
| Verification at baseline | 90 tests passed; 100% statement and branch coverage; Ruff and mypy --strict clean; CI passing on Ubuntu and macOS |

The `v1.0.0` tag is immutable. It is never moved, deleted or re-created.

### 2.1 Changes after the baseline

| Commit | Description | Affects algorithm? |
|---|---|---|
| `36c98f4` | Dependabot: bump `actions/checkout` from v5 to v7 (CI only) | No |
| `01a136d` | Merge of pull request #7 | No |

This was verified on 13 November 2026 with:

```bash
git diff --stat v1.0.0 main -- src config tests
```

The command produced no output, confirming that the source, configuration and tests on `main` are identical to the v1.0.0 baseline.

## 3. Versioning

[Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`) is used:

- **MAJOR**: incompatible change to inputs, outputs or behaviour.
- **MINOR**: new backwards-compatible functionality (e.g. a new detection function).
- **PATCH**: backwards-compatible fault correction.

The package version in `pyproject.toml` is changed only at release, after verification and review are complete. During development, the state of the software is identified by branch name and commit hash.

## 4. Branching and integration rules

- `main` holds only reviewed, verified software. It is protected by the `protect-main` ruleset:
  - changes only through pull requests;
  - both CI checks must pass (`Lint, type-check and test (ubuntu-latest)` and `(macos-latest)`);
  - force pushes blocked; branch deletion restricted.
- Work is carried out on short-lived branches named by purpose: `docs/…`, `test/…`, `feat/…`, `fix/…`.
- Commit messages follow the Conventional Commits style (`feat:`, `fix:`, `test:`, `docs:`, `build:`, `ci:`, `chore:`).
- Branches are deleted after merging. History on `main` is never rewritten.

## 5. Change control process

1. **Identify:** a problem or improvement is found, normally through testing.
2. **Record:** a change request (CR) is raised as a GitHub issue and documented in `docs/CR-nnn-*.md`. It states the problem, evidence, proposed change, affected requirements, impact and acceptance criteria.
3. **Approve:** the CR is approved before implementation begins.
4. **Implement:** the change is made on a dedicated branch, referencing the CR.
5. **Verify:** the full regression suite and CR-specific tests pass locally and in CI.
6. **Review:** the change is reviewed against `docs/REVIEW.md`, and the findings are recorded.
7. **Merge:** the pull request is merged into `main` after CI passes and the review is complete.
8. **Release:** the version is updated, `CHANGELOG.md` is updated, and a new tag and GitHub release are created.

## 6. Configuration status accounting

| Record | Purpose |
|---|---|
| Git history and tags | Who changed what, when and why |
| Pull requests | Change content, CI results and review |
| GitHub issues | Change requests |
| `CHANGELOG.md` | Human-readable summary of changes by version |
| `results/` | Verification evidence for each version |

## 7. Configuration audit commands

```bash
git show -s --format='%H %ad %s' v1.0.0     # identify the baseline
git log --oneline v1.0.0..main              # changes since the baseline
git diff --stat v1.0.0 main -- src config tests   # algorithm changes since the baseline
git tag -n                                  # list releases
```
