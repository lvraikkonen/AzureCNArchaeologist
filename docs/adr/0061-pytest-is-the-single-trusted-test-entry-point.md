# pytest Is the Single Trusted Test Entry Point

Status: Accepted

v0.4 establishes `uv run pytest` as the only formal test entry point, with pytest declared in the development environment, collection restricted to `tests/`, and strict configuration and marker enforcement. Existing `unittest.TestCase` suites remain collected during migration, but collection errors, zero collected tests, missing required fixtures, and unknown markers fail; skips require explicit reason codes. Print-only diagnostics, log messages containing success text, and test-like files elsewhere in the repository do not contribute to a green result, because multiple runners and informal scripts previously allowed incompatible definitions of test success.
