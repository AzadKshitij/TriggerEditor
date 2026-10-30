"""Windows Task Scheduler helpers (plan 08 3.10, S10). Qt-free.

Everything that talks to the operating system goes through
:func:`_run_schtasks`, so tests replace one function. No password is ever
accepted or stored; ``--run-whether-logged-on`` uses ``S4U`` (no network
credentials) and the default is ``InteractiveToken``.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from trigger_designer.core.headless.atomic import write_bytes_atomic, write_json_atomic
from trigger_designer.core.headless.exit_codes import CliError, ExitCode

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TASK_FOLDER = "TriggerDesigner"
TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
DAYS = {
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday",
    "SUN": "Sunday",
}
NON_WINDOWS_MESSAGE = (
    "Scheduling is implemented for Windows Task Scheduler only; call the CLI "
    "from cron, systemd or launchd instead (see docs/CLI.md)."
)


@dataclass
class ScheduleSpec:
    name: str
    workflow: str
    workflow_sha256: str
    trigger: dict
    params: dict = field(default_factory=dict)
    run_whether_logged_on: bool = False
    skip_missed: bool = False
    timeout_s: int = 3600
    max_memory_mb: int | None = None
    state_dir: str = ""
    log_file: str = ""
    xml_path: str = ""
    created_at: str = ""
    user: str = ""
    now: datetime | None = None

    @property
    def task_name(self) -> str:
        return f"{TASK_FOLDER}\\{self.name}"


# ------------------------------------------------------------------ triggers
def _hhmm(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text.strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            f"'{text}' is not a time of day.",
            "Use 24-hour HH:MM, for example 02:30.",
        )
    return int(match.group(1)), int(match.group(2))


def parse_trigger(
    *,
    daily: str | None = None,
    weekdays: str | None = None,
    weekly: str | None = None,
    hourly: int | None = None,
    once: str | None = None,
) -> dict:
    """The trigger as a plain dict (stored in the schedule's JSON)."""
    if daily:
        hour, minute = _hhmm(daily)
        return {"kind": "daily", "time": f"{hour:02d}:{minute:02d}"}
    if weekdays:
        hour, minute = _hhmm(weekdays)
        return {"kind": "weekdays", "time": f"{hour:02d}:{minute:02d}"}
    if weekly:
        days_text, sep, time_text = weekly.partition("@")
        if not sep:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"'{weekly}' must look like MON,THU@06:30.",
            )
        days = [d.strip().upper()[:3] for d in days_text.split(",") if d.strip()]
        bad = [d for d in days if d not in DAYS]
        if not days or bad:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Unknown day {', '.join(bad) or '(none)'} in '{weekly}'.",
                "Use MON, TUE, WED, THU, FRI, SAT, SUN.",
            )
        hour, minute = _hhmm(time_text)
        return {
            "kind": "weekly",
            "days": list(dict.fromkeys(days)),
            "time": f"{hour:02d}:{minute:02d}",
        }
    if hourly is not None:
        if not 1 <= int(hourly) <= 720:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                "--hourly needs a whole number from 1 to 720.",
            )
        return {"kind": "hourly", "every": int(hourly)}
    if once:
        try:
            when = datetime.strptime(once.strip(), "%Y-%m-%dT%H:%M")
        except ValueError:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"'{once}' is not a date and time.",
                "Use YYYY-MM-DDTHH:MM, for example 2026-11-02T06:30.",
            ) from None
        return {"kind": "once", "at": when.strftime("%Y-%m-%dT%H:%M")}
    raise CliError(ExitCode.USAGE, "TD-CLI-006", "Choose when the task should run.")


def _boundary(date: datetime, hhmm: str) -> str:
    hour, minute = _hhmm(hhmm)
    return f"{date:%Y-%m-%d}T{hour:02d}:{minute:02d}:00"


def trigger_xml(trigger: dict, now: datetime | None = None) -> str:
    now = now or datetime.now()
    kind = trigger["kind"]
    if kind == "daily":
        return (
            "<CalendarTrigger>"
            f"<StartBoundary>{_boundary(now, trigger['time'])}</StartBoundary>"
            "<Enabled>true</Enabled>"
            "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
            "</CalendarTrigger>"
        )
    if kind in ("weekdays", "weekly"):
        days = (
            ["MON", "TUE", "WED", "THU", "FRI"]
            if kind == "weekdays"
            else trigger["days"]
        )
        day_xml = "".join(f"<{DAYS[d]} />" for d in days)
        return (
            "<CalendarTrigger>"
            f"<StartBoundary>{_boundary(now, trigger['time'])}</StartBoundary>"
            "<Enabled>true</Enabled>"
            "<ScheduleByWeek><WeeksInterval>1</WeeksInterval>"
            f"<DaysOfWeek>{day_xml}</DaysOfWeek></ScheduleByWeek>"
            "</CalendarTrigger>"
        )
    if kind == "hourly":
        return (
            "<TimeTrigger>"
            f"<StartBoundary>{now:%Y-%m-%dT%H:%M}:00</StartBoundary>"
            "<Enabled>true</Enabled>"
            f"<Repetition><Interval>PT{trigger['every']}H</Interval></Repetition>"
            "</TimeTrigger>"
        )
    if kind == "once":
        return (
            "<TimeTrigger>"
            f"<StartBoundary>{trigger['at']}:00</StartBoundary>"
            "<Enabled>true</Enabled></TimeTrigger>"
        )
    raise CliError(ExitCode.INTERNAL, "TD-SYS-999", f"Unknown trigger kind {kind!r}.")


# ------------------------------------------------------------------- command
def executable() -> list[str]:
    """The program a task starts: the frozen CLI, or ``python -m`` in development."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "trigger_designer.cli"]


def build_command(spec: ScheduleSpec) -> list[str]:
    """The exact command line the scheduled task runs."""
    command = [*executable()]
    if spec.state_dir:
        command += ["--state-dir", spec.state_dir]
    command += ["run", spec.workflow]
    for name, value in spec.params.items():
        command += ["--param", f"{name}={value}"]
    command += ["--trigger", "schedule", "--log-format", "json"]
    if spec.log_file:
        command += ["--log-file", spec.log_file]
    command += ["--timeout", str(spec.timeout_s)]
    if spec.max_memory_mb:
        command += ["--max-memory", str(spec.max_memory_mb)]
    return command


def _principal_user() -> str:
    domain, user = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    if not user:
        import getpass

        user = getpass.getuser()
    return f"{domain}\\{user}" if domain else user


def build_task_xml(spec: ScheduleSpec) -> str:
    command = build_command(spec)
    exe, args = command[0], subprocess.list2cmdline(command[1:])
    logon = "S4U" if spec.run_whether_logged_on else "InteractiveToken"
    limit = int(spec.timeout_s) + 300
    description = (
        f"trigger-designer-cli run of {spec.workflow} "
        f"(sha256 {spec.workflow_sha256[:16]}...)"
    )
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        f'<Task version="1.2" xmlns="{TASK_NS}">\n'
        f"  <RegistrationInfo><Description>{escape(description)}</Description>"
        f"<URI>\\{escape(spec.task_name)}</URI></RegistrationInfo>\n"
        f"  <Triggers>{trigger_xml(spec.trigger, spec.now)}</Triggers>\n"
        f'  <Principals><Principal id="Author"><UserId>{escape(spec.user or _principal_user())}</UserId>'
        f"<LogonType>{logon}</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>\n"
        "  <Settings>\n"
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        f"    <StartWhenAvailable>{'false' if spec.skip_missed else 'true'}</StartWhenAvailable>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <WakeToRun>false</WakeToRun>\n"
        f"    <ExecutionTimeLimit>PT{limit}S</ExecutionTimeLimit>\n"
        "    <Enabled>true</Enabled>\n"
        "  </Settings>\n"
        '  <Actions Context="Author"><Exec>'
        f"<Command>{escape(exe)}</Command><Arguments>{escape(args)}</Arguments>"
        f"<WorkingDirectory>{escape(os.path.dirname(spec.workflow))}</WorkingDirectory>"
        "</Exec></Actions>\n"
        "</Task>\n"
    )


def xml_bytes(xml: str) -> bytes:
    """UTF-16 with a byte-order mark: the encoding Windows itself exports."""
    return xml.encode("utf-16")


# ------------------------------------------------------------------ schtasks
def _run_schtasks(argv: list[str]) -> subprocess.CompletedProcess:
    """The only place a subprocess is started."""
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
        check=False,
    )


def create_argv(spec: ScheduleSpec) -> list[str]:
    return ["schtasks", "/Create", "/TN", spec.task_name, "/XML", spec.xml_path, "/F"]


def delete_argv(name: str) -> list[str]:
    return ["schtasks", "/Delete", "/TN", f"{TASK_FOLDER}\\{name}", "/F"]


def query_argv() -> list[str]:
    return ["schtasks", "/Query", "/FO", "CSV", "/V"]


def ensure_windows() -> None:
    if not sys.platform.startswith("win"):
        raise CliError(ExitCode.SCHEDULER, "TD-CLI-016", NON_WINDOWS_MESSAGE)


def scheduler_error(action: str, proc: subprocess.CompletedProcess) -> CliError:
    text = (proc.stderr or proc.stdout or "").strip()
    hint = "Read the message from Windows above; run from an account allowed to create tasks."
    if "denied" in text.lower():
        hint = (
            "Access was denied. Use the default (logged-on only) mode, or run from "
            "an account that may create tasks."
        )
    return CliError(
        ExitCode.SCHEDULER,
        "TD-CLI-016",
        f"schtasks {action} failed (exit {proc.returncode}): {text}",
        hint,
    )


def parse_query_csv(text: str) -> list[dict]:
    """Rows of ``schtasks /Query /FO CSV /V`` for our folder, parsed by position
    (headers are localized and dates are locale-formatted: both kept raw)."""
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 7 or not row[1].lower().startswith(f"\\{TASK_FOLDER}\\".lower()):
            continue
        last = row[6].strip()
        rows.append(
            {
                "task_name": row[1],
                "name": row[1].rsplit("\\", 1)[-1],
                "next_run": row[2],
                "status": row[3],
                "last_run": row[5],
                "last_result": int(last) if re.fullmatch(r"-?\d+", last) else last,
            }
        )
    return rows


# ------------------------------------------------------------------ storage
def schedules_dir(state: Path) -> Path:
    path = Path(state) / "schedules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def definition(spec: ScheduleSpec) -> dict:
    return {
        "version": 1,
        "name": spec.name,
        "task_name": spec.task_name,
        "workflow": spec.workflow,
        "workflow_sha256": spec.workflow_sha256,
        "params": spec.params,
        "trigger": spec.trigger,
        "run_whether_logged_on": spec.run_whether_logged_on,
        "skip_missed": spec.skip_missed,
        "timeout_s": spec.timeout_s,
        "max_memory_mb": spec.max_memory_mb,
        "created_at": spec.created_at,
        "command": build_command(spec),
        "xml_path": spec.xml_path,
    }


def save_spec(spec: ScheduleSpec) -> None:
    folder = Path(spec.xml_path).parent
    write_bytes_atomic(Path(spec.xml_path), xml_bytes(build_task_xml(spec)))
    write_json_atomic(folder / f"{spec.name}.json", definition(spec))


def load_definitions(state: Path) -> list[dict]:
    import json

    found = []
    folder = Path(state) / "schedules"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            found.append({"name": path.stem, "broken": str(exc), "trigger": {}})
    return found


def check_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            f"'{name}' is not a valid schedule name.",
            "Use letters, digits, - and _ (up to 64 characters), starting with a letter or digit.",
        )
