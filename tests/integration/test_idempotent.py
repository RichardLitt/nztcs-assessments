"""Two runs over the same input must produce byte-identical review/ output.

Catches non-determinism (set/dict ordering, timestamps) leaking into files. The
second run uses a fresh cache so both runs exercise the network path.
"""

from tests.integration.test_end_to_end import _files, run_cli


def test_two_runs_identical(tmp_path):
    first = run_cli(tmp_path, "first")
    second = run_cli(tmp_path, "second")
    assert _files(first) == _files(second)


def test_cached_rerun_identical(tmp_path):
    first = run_cli(tmp_path, "same")
    snapshot = _files(first)
    rerun = run_cli(tmp_path, "same")  # same out + cache dir: served from disk
    assert _files(rerun) == snapshot
