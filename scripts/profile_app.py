"""Profile the TriggerEditor application with cProfile + tracemalloc + psutil.

Generates a .prof file (browse it with the stdlib: ``python -m pstats
profiles/latest.prof``) and prints a terminal summary of hotspots and
memory. Every Python-memory number is printed beside the process RSS:
Polars' Rust heap, DuckDB's C++ heap, PyArrow buffers and Qt never pass
through CPython's allocator, so a tracemalloc total alone understates the
app. For the native-vs-Python split use scalene (recipe below).

Usage
-----
    # Run and profile (app opens normally - close it when done):
    uv run --group profiling python scripts/profile_app.py

    # Self-exiting run, sized for an external sampling profiler. The modal
    # welcome dialog is skipped (process-local patch): it waits for a human
    # and would outlive the deadline.
    uv run --group profiling python scripts/profile_app.py --profile-seconds 60

    # Leak-hunt mode: diff the live heap at exit against the heap when the
    # event loop started, so a one-time cost is never read as growth:
    uv run --group profiling python scripts/profile_app.py --snapshot-diff

    # tracemalloc off, for measuring this instrument's own overhead:
    uv run --group profiling python scripts/profile_app.py --no-tracemalloc

    # Optional: pass a .tds file to open on launch
    uv run --group profiling python scripts/profile_app.py path/to/file.tds

    # Per-line CPU + Python/native memory + copy volume across the
    # Python/C++ boundary. PYTHONUTF8=1 or the table headers are cp1252
    # mojibake; the program MUST exit on its own (a killed process writes
    # truncated JSON that `scalene view` rejects):
    #   set PYTHONUTF8=1
    #   .venv\\Scripts\\python.exe -m scalene run --memory \\
    #       -o profiles\\scalene.json scripts\\profile_app.py --profile-seconds 60
    #   .venv\\Scripts\\python.exe -m scalene view --cli profiles\\scalene.json
"""

import argparse
import atexit
import cProfile
import datetime
import io
import pstats
import sys
import threading
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFILES_DIR = ROOT / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

_SEP = "=" * 70

#: tracemalloc frame depth. 5 is enough to attribute growth to its call
#: site; deeper traces mainly cost memory in the tracer itself.
_TRACE_DEPTH = 5

#: RSS sampling period for the monitor thread. Memory grows slowly enough
#: that a quarter-second poll never misses the high-water mark that
#: matters; it does not need to see 250 ms bumps.
_RSS_POLL_S = 0.25


def _print_cprofile_summary(pr: cProfile.Profile) -> None:
    print(f"\n{_SEP}")
    print("TOP 30  -  CUMULATIVE TIME  (most expensive call chains)")
    print(_SEP)
    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream)
    ps.sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(30)
    print(stream.getvalue())

    print(_SEP)
    print("TOP 30  -  TOTAL (SELF) TIME  (functions doing the most work)")
    print(_SEP)
    stream2 = io.StringIO()
    ps2 = pstats.Stats(pr, stream=stream2)
    ps2.sort_stats(pstats.SortKey.TIME)
    ps2.print_stats(30)
    print(stream2.getvalue())

    print(_SEP)
    print("TOP 30  -  CALL COUNT  (most-called functions)")
    print(_SEP)
    stream3 = io.StringIO()
    ps3 = pstats.Stats(pr, stream=stream3)
    ps3.sort_stats(pstats.SortKey.CALLS)
    ps3.print_stats(30)
    print(stream3.getvalue())


def _print_memory_summary(snapshot: tracemalloc.Snapshot) -> None:
    print(_SEP)
    print("TOP 25  -  MEMORY ALLOCATIONS BY LINE  (tracemalloc)")
    print(_SEP)
    top = snapshot.statistics("lineno")
    for i, stat in enumerate(top[:25], 1):
        frame = stat.traceback[0]
        size_kb = stat.size / 1024
        print(f"  {i:>2}. {size_kb:>9.1f} KB  -  {frame.filename}:{frame.lineno}")
    total_kb = sum(s.size for s in top) / 1024
    print(f"\n  Total tracked (CPython only): {total_kb:.1f} KB")
    print("  (Rust/C++/Arrow/Qt allocations do not appear here - read the")
    print("   RSS numbers beside it, or run under scalene for the split.)\n")

    print(_SEP)
    print("TOP 10  -  MEMORY ALLOCATIONS BY FILE  (tracemalloc)")
    print(_SEP)
    by_file = snapshot.statistics("filename")
    for i, stat in enumerate(by_file[:10], 1):
        frame = stat.traceback[0]
        size_kb = stat.size / 1024
        print(f"  {i:>2}. {size_kb:>9.1f} KB  -  {frame.filename}")


def _print_snapshot_diff(
    before: tracemalloc.Snapshot, after: tracemalloc.Snapshot
) -> None:
    """What the session left behind, not what it holds at any instant."""
    print(f"\n{_SEP}")
    print("TOP 25  -  GROWTH SINCE EVENT-LOOP START (snapshot diff)")
    print(_SEP)
    diff = after.compare_to(before, "lineno")
    total_growth = sum(d.size_diff for d in diff if d.size_diff > 0)
    for i, stat in enumerate(diff[:25], 1):
        frame = stat.traceback[0]
        sign = "+" if stat.size_diff >= 0 else ""
        print(
            f"  {i:>2}. {sign}{stat.size_diff / 1024:>9.1f} KB  "
            f"(net {stat.size / 1024:.1f} KB, {stat.count_diff:+d} blocks)  "
            f"-  {frame.filename}:{frame.lineno}"
        )
    print(f"\n  Total growth line-attributed: {total_growth / 1024:.1f} KB")
    print("  One-time cost vs leak: repeat the session and diff again - a")
    print("  leak keeps growing, a one-time cost shows a flat second diff.")


class _RssWatcher:
    """Background RSS high-water + the optional self-exit countdown.

    The main thread belongs to Qt's event loop, so this thread only reads
    /proc-equivalent numbers and, when asked, posts a queued ``quit()``
    into the main thread - the documented thread-safe route, since a
    QTimer armed here would need an event dispatcher this thread does not
    run. ``psutil`` is already a runtime dependency.

    ``on_loop_start`` fires once, from this thread, the moment the
    QApplication first exists: the snapshot-diff baseline is taken when
    the event loop is live, so boot imports are not counted as "growth".
    """

    def __init__(
        self,
        profile_seconds: float | None,
        on_loop_start: Callable[[], None] = lambda: None,
    ) -> None:
        self.peak_rss_mb = 0.0
        self.final_rss_mb = 0.0
        self._stop = threading.Event()
        self._profile_seconds = profile_seconds
        self._on_loop_start = on_loop_start
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    # -- internals ---------------------------------------------------------
    def _run(self) -> None:
        import psutil
        from qtpy.QtCore import QMetaObject, Qt
        from qtpy.QtWidgets import QApplication

        process = psutil.Process()
        quit_at = None
        while not self._stop.is_set():
            self._stop.wait(_RSS_POLL_S)
            rss_mb = process.memory_info().rss / (1024 * 1024)
            self.peak_rss_mb = max(self.peak_rss_mb, rss_mb)
            self.final_rss_mb = rss_mb
            if self._profile_seconds is None:
                continue
            app = QApplication.instance()
            if app is None:
                # Event loop not up yet; the countdown starts at "app is
                # up", not at process start, so slow imports never cut
                # the profiled session short.
                continue
            if quit_at is None:
                quit_at = time.monotonic() + self._profile_seconds
                self._on_loop_start()
            if time.monotonic() >= quit_at:
                # Post on every poll, not once: a modal dialog's nested
                # event loop swallows the first quit, and the main loop
                # needs its own. Whichever loop is innermost exits, then
                # the next post catches the one below it.
                QMetaObject.invokeMethod(
                    app, "quit", Qt.ConnectionType.QueuedConnection
                )


def _suppress_welcome_dialog() -> None:
    """Skip the modal startup dialog during an automated run.

    ``TriggerWindow.showWelcomeDialogIfNeeded`` calls ``dialog.exec()`` - a
    nested event loop that waits for a human to click. A ``--profile-seconds``
    run would spend its whole window on an idle dialog (and outlive the
    deadline). Patching the preference getter keeps this process-local: no
    setting is read or written, so an interactive run still shows the dialog.
    """
    from trigger_designer.qt.helpers.recent_files import RecentFilesManager

    RecentFilesManager.is_welcome_enabled = lambda self: False  # type: ignore[method-assign]


def run(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("tds", nargs="?", help=".tds workflow to open on launch")
    parser.add_argument(
        "--profile-seconds",
        type=float,
        default=None,
        help="quit the app this many seconds after its event loop starts "
        "(a killed process under scalene writes truncated JSON; this exits "
        "cleanly instead)",
    )
    parser.add_argument(
        "--snapshot-diff",
        action="store_true",
        help="also diff the exit heap against the heap at event-loop start",
    )
    parser.add_argument(
        "--no-tracemalloc",
        action="store_true",
        help="skip tracemalloc (for measuring this instrument's own overhead)",
    )
    args = parser.parse_args(argv)

    # main() hands sys.argv to QApplication; keep only the script path and
    # any .tds argument so Qt never sees our own flags.
    sys.argv = [sys.argv[0]] + ([args.tds] if args.tds else [])

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prof_path = PROFILES_DIR / f"profile_{timestamp}.prof"
    latest_path = PROFILES_DIR / "latest.prof"

    def _save_profile() -> None:
        """Dump stats to disk - registered with atexit as a safety net."""
        if pr.getstats():
            try:
                pr.dump_stats(str(prof_path))
                pr.dump_stats(str(latest_path))
                print(f"\n[profiler] Saved: {prof_path}")
            except Exception as exc:  # noqa: BLE001 - losing stats beats
                # crashing the app's exit path over the profiler's own work
                print(f"\n[profiler] WARNING: could not save profile: {exc}")

    if not args.no_tracemalloc:
        tracemalloc.start(_TRACE_DEPTH)
    pr = cProfile.Profile()

    # cProfile takes over sys.setprofile; a tool that got there first
    # (scalene runs this script as its target) makes enable() raise. Skip
    # ours rather than fail - the external profiler is the better
    # instrument, and the RSS reader plus tracemalloc still work.
    cprofile_on = True
    try:
        pr.enable()
    except ValueError:
        cprofile_on = False
        print(
            "[profiler] Another profiler owns the profile hook (scalene?); "
            "cProfile skipped, RSS + tracemalloc summaries still run."
        )

    # Register as atexit backup in case os._exit() is called by Qt
    if cprofile_on:
        atexit.register(_save_profile)

    before_snapshot: tracemalloc.Snapshot | None = None

    def _take_before() -> None:
        nonlocal before_snapshot
        if args.snapshot_diff and not args.no_tracemalloc:
            before_snapshot = tracemalloc.take_snapshot()

    watcher = _RssWatcher(args.profile_seconds, on_loop_start=_take_before)
    watcher.start()

    if args.profile_seconds is not None:
        _suppress_welcome_dialog()

    t_start = time.monotonic()
    try:
        from trigger_designer.main import main

        main()
    except SystemExit:
        # Qt calls sys.exit(app.exec()) on close - that's expected
        pass
    finally:
        if cprofile_on:
            pr.disable()
        wall = time.monotonic() - t_start
        watcher.stop()

        # Save profile first - before anything else that could raise
        if cprofile_on:
            _save_profile()
            atexit.unregister(_save_profile)  # prevent double-write on normal exit

        print(f"\n{_SEP}")
        print("PROFILING COMPLETE")
        print(_SEP)
        if cprofile_on:
            print(f"  Profile file : {prof_path}")
            print(f"  Latest alias : {latest_path}")
        else:
            print("  cProfile     : skipped (external profiler owns the hook)")
        print()
        if cprofile_on:
            print("  Browse the .prof (stdlib, no extra install):")
            print(f"    python -m pstats {latest_path}")
        print("  Per-line CPU + Python/native memory + copy volume (scalene):")
        print("    set PYTHONUTF8=1")
        print(
            "    .venv\\Scripts\\python.exe -m scalene run --memory "
            "-o profiles\\scalene.json \\"
        )
        print("        scripts\\profile_app.py --profile-seconds 60")
        print(
            "    .venv\\Scripts\\python.exe -m scalene view --cli "
            "profiles\\scalene.json"
        )
        print(_SEP)

        if cprofile_on:
            _print_cprofile_summary(pr)

        print(_SEP)
        print("PROCESS MEMORY (psutil - the native-heap floor truth)")
        print(_SEP)
        print(f"  Wall time run   : {wall:.1f} s")
        print(f"  Peak RSS        : {watcher.peak_rss_mb:.1f} MB")
        print(f"  Final RSS       : {watcher.final_rss_mb:.1f} MB")

        after_snapshot = None
        if not args.no_tracemalloc:
            try:
                after_snapshot = tracemalloc.take_snapshot()
            except Exception as exc:  # noqa: BLE001 - same safety net:
                # never let the instrument's own teardown raise during exit
                print(f"[profiler] WARNING: tracemalloc snapshot failed: {exc}")
            finally:
                tracemalloc.stop()

        if after_snapshot is not None:
            print()
            _print_memory_summary(after_snapshot)
            if before_snapshot is not None:
                _print_snapshot_diff(before_snapshot, after_snapshot)


if __name__ == "__main__":
    run(sys.argv[1:])
