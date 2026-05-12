"""Profile the TriggerEditor application using cProfile + tracemalloc.

Generates a .prof file viewable with SnakeViz and prints a terminal summary
of the top hotspot functions and memory allocators.

Usage
-----
    # Run and profile (app opens normally - close it when done):
    uv run --group profiling python scripts/profile_app.py

    # Open the interactive visual report:
    uv run --group profiling snakeviz profiles/latest.prof

    # Optional: pass a .tds file to open on launch
    uv run --group profiling python scripts/profile_app.py path/to/file.tds
"""

import atexit
import cProfile
import datetime
import io
import pstats
import sys
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFILES_DIR = ROOT / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

_SEP = "=" * 70


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
    print(f"\n  Total tracked: {total_kb:.1f} KB\n")

    print(_SEP)
    print("TOP 10  -  MEMORY ALLOCATIONS BY FILE  (tracemalloc)")
    print(_SEP)
    by_file = snapshot.statistics("filename")
    for i, stat in enumerate(by_file[:10], 1):
        frame = stat.traceback[0]
        size_kb = stat.size / 1024
        print(f"  {i:>2}. {size_kb:>9.1f} KB  -  {frame.filename}")


def run() -> None:
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
            except Exception as exc:
                print(f"\n[profiler] WARNING: could not save profile: {exc}")

    tracemalloc.start(25)  # keep 25-frame tracebacks for richer context
    pr = cProfile.Profile()

    # Register as atexit backup in case os._exit() is called by Qt
    atexit.register(_save_profile)

    pr.enable()
    try:
        from trigger_designer.main import main
        main()
    except SystemExit:
        # Qt calls sys.exit(app.exec()) on close - that's expected
        pass
    finally:
        pr.disable()

        # Save profile first - before anything else that could raise
        _save_profile()
        atexit.unregister(_save_profile)  # prevent double-write on normal exit

        snapshot = None
        try:
            snapshot = tracemalloc.take_snapshot()
        except Exception as exc:
            print(f"[profiler] WARNING: tracemalloc snapshot failed: {exc}")
        finally:
            tracemalloc.stop()

        print(f"\n{_SEP}")
        print("PROFILING COMPLETE")
        print(_SEP)
        print(f"  Profile file : {prof_path}")
        print(f"  Latest alias : {latest_path}")
        print()
        print("  Open SnakeViz (interactive flame/icicle chart):")
        print(f"    uv run --group profiling snakeviz {latest_path}")
        print()
        print("  Filter to your code only:")
        print(f"    uv run --group profiling snakeviz --server {latest_path}")
        print(_SEP)

        _print_cprofile_summary(pr)
        if snapshot is not None:
            _print_memory_summary(snapshot)


if __name__ == "__main__":
    run()
