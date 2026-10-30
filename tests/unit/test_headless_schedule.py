"""Scheduling with ``_run_schtasks`` mocked: nothing here creates a real task."""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from tests.support.cli import call_main, synthetic_workflow, write_workflow
from trigger_designer.core.headless import schedule as sched
from trigger_designer.core.headless.approvals import make_entry, store_for
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.workflow_file import read_workflow

NS = {"t": sched.TASK_NS}

# Real shape of ``schtasks /Query /FO CSV /V`` on a French machine: localized
# header, locale dates (X10), one row per trigger.
FRENCH_CSV = (
    '"NomHote","NomTache","Prochaine exécution","Statut","Mode d\'ouverture de session",'
    '"Heure de la dernière exécution","Dernier résultat","Auteur","Tâche à exécuter"\r\n'
    '"BOX","\\Microsoft\\Windows\\X","N/A","Prêt","Interactif","N/A","0","MS","c:\\x.exe"\r\n'
    '"BOX","\\TriggerDesigner\\nightly","22-10-2026 13:00:00","Prêt","Interactif seulement",'
    '"21-10-2026 13:00:00","0","me","c:\\python.exe -m trigger_designer.cli"\r\n'
    '"BOX","\\TriggerDesigner\\broken","N/A","Désactivé","Interactif seulement",'
    '"N/A","267011","me","c:\\python.exe"\r\n'
)


class Recorder:
    """Stands in for ``_run_schtasks``; records every argv."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.calls: list[list[str]] = []
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)
        self.by_verb: dict[str, subprocess.CompletedProcess] = {}

    def __call__(self, argv):
        self.calls.append(list(argv))
        return self.by_verb.get(argv[1], self.result)


@pytest.fixture(autouse=True)
def on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")


@pytest.fixture
def fake(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(sched, "_run_schtasks", rec)
    return rec


@pytest.fixture
def approved(tmp_path):
    path = write_workflow(
        tmp_path / "my flows" / "r\xe9sum\xe9 wf.tds",
        synthetic_workflow(
            input_path=str(tmp_path / "in.csv"), output_path=str(tmp_path / "o.csv")
        ),
    )
    store_for(tmp_path / "state").add(make_entry(read_workflow(str(path)), [], []))
    return path


def _env(tmp_path):
    return {"TRIGGER_DESIGNER_STATE_DIR": str(tmp_path / "state")}


def _add(tmp_path, wf, *extra, name="nightly"):
    return call_main(
        ["schedule", "add", name, wf, "--daily", "02:30", *extra], env=_env(tmp_path)
    )


def _spec(**kw):
    base = {
        "name": "nightly",
        "workflow": "C:\\data\\r\xe9sum\xe9 wf.tds",
        "workflow_sha256": "ab" * 32,
        "trigger": {"kind": "daily", "time": "02:30"},
        "timeout_s": 3600,
        "xml_path": "C:\\state\\schedules\\nightly.xml",
        "user": "BOX\\me",
        "now": datetime(2026, 10, 30, 9, 0),
    }
    base.update(kw)
    return sched.ScheduleSpec(**base)


def _xml(spec):
    return ET.fromstring(sched.build_task_xml(spec).split("\n", 1)[1])


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"daily": "2:05"}, {"kind": "daily", "time": "02:05"}),
        ({"weekdays": "06:30"}, {"kind": "weekdays", "time": "06:30"}),
        (
            {"weekly": "MON,thu@06:30"},
            {"kind": "weekly", "days": ["MON", "THU"], "time": "06:30"},
        ),
        ({"hourly": 6}, {"kind": "hourly", "every": 6}),
        ({"once": "2026-11-02T06:30"}, {"kind": "once", "at": "2026-11-02T06:30"}),
    ],
)
def test_parse_trigger(kwargs, expected):
    assert sched.parse_trigger(**kwargs) == expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"daily": "25:00"},
        {"daily": "9"},
        {"weekly": "FUNDAY@01:00"},
        {"weekly": "MON 01:00"},
        {"hourly": 0},
        {"once": "tomorrow"},
        {},
    ],
)
def test_parse_trigger_rejects(kwargs):
    with pytest.raises(CliError):
        sched.parse_trigger(**kwargs)


def test_task_xml_structure():
    spec = _spec(params={"input_file": "C:\\in put\\a.csv"})
    root = _xml(spec)
    assert root.find("t:Settings/t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
    assert root.find("t:Settings/t:StartWhenAvailable", NS).text == "true"
    assert root.find("t:Settings/t:ExecutionTimeLimit", NS).text == "PT3900S"
    assert (
        root.find("t:Principals/t:Principal/t:LogonType", NS).text == "InteractiveToken"
    )
    assert root.find("t:Principals/t:Principal/t:RunLevel", NS).text == "LeastPrivilege"
    command = sched.build_command(spec)
    exe = root.find("t:Actions/t:Exec/t:Command", NS).text
    args = root.find("t:Actions/t:Exec/t:Arguments", NS).text
    assert exe == command[0]
    assert args == subprocess.list2cmdline(command[1:])
    assert "r\xe9sum\xe9 wf.tds" in args and '"input_file=C:\\in put\\a.csv"' in args
    assert root.find("t:Actions/t:Exec/t:WorkingDirectory", NS).text == "C:\\data"
    day = root.find("t:Triggers/t:CalendarTrigger", NS)
    assert day.find("t:StartBoundary", NS).text == "2026-10-30T02:30:00"
    assert day.find("t:ScheduleByDay/t:DaysInterval", NS).text == "1"


def test_trigger_variants_in_xml():
    weekly = _xml(
        _spec(trigger={"kind": "weekly", "days": ["MON", "THU"], "time": "06:30"})
    )
    days = weekly.find("t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek", NS)
    assert [d.tag.rsplit("}", 1)[-1] for d in days] == ["Monday", "Thursday"]
    weekdays = _xml(_spec(trigger={"kind": "weekdays", "time": "06:30"}))
    days = weekdays.find(
        "t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek", NS
    )
    assert len(days) == 5
    hourly = _xml(_spec(trigger={"kind": "hourly", "every": 6}))
    assert (
        hourly.find("t:Triggers/t:TimeTrigger/t:Repetition/t:Interval", NS).text
        == "PT6H"
    )
    assert hourly.find("t:Triggers/t:TimeTrigger/t:Repetition/t:Duration", NS) is None
    once = _xml(_spec(trigger={"kind": "once", "at": "2030-01-01T06:30"}))
    assert (
        once.find("t:Triggers/t:TimeTrigger/t:StartBoundary", NS).text
        == "2030-01-01T06:30:00"
    )


def test_xml_escapes_special_characters():
    spec = _spec(workflow="C:\\a&b\\<x>.tds")
    root = _xml(spec)  # parses: nothing broke the document
    assert "a&b" in root.find("t:Actions/t:Exec/t:Arguments", NS).text


def test_run_whether_logged_on_uses_s4u_and_never_a_password(tmp_path, approved, fake):
    result = _add(tmp_path, approved, "--run-whether-logged-on")
    assert result.code == 0, result.stderr
    xml = ET.fromstring(
        Path(tmp_path / "state" / "schedules" / "nightly.xml")
        .read_bytes()
        .decode("utf-16")
        .split("\n", 1)[1]
    )
    assert xml.find("t:Principals/t:Principal/t:LogonType", NS).text == "S4U"
    flat = [a for call in fake.calls for a in call]
    assert not {"/RP", "/RU", "/P"} & set(flat)


def test_skip_missed_sets_false():
    assert (
        _xml(_spec(skip_missed=True)).find("t:Settings/t:StartWhenAvailable", NS).text
        == "false"
    )


def test_xml_file_is_utf16_with_bom(tmp_path, approved, fake):
    assert _add(tmp_path, approved).code == 0
    raw = (tmp_path / "state" / "schedules" / "nightly.xml").read_bytes()
    assert raw[:2] in (b"\xff\xfe", b"\xfe\xff")
    assert "TriggerDesigner" in raw.decode("utf-16")


def test_add_calls_create_with_exact_argv(tmp_path, approved, fake):
    result = _add(tmp_path, approved)
    assert result.code == 0, result.stderr
    xml_path = str(tmp_path / "state" / "schedules" / "nightly.xml")
    assert fake.calls == [
        [
            "schtasks",
            "/Create",
            "/TN",
            "TriggerDesigner\\nightly",
            "/XML",
            xml_path,
            "/F",
        ]
    ]
    definition = json.loads(
        (tmp_path / "state" / "schedules" / "nightly.json").read_text()
    )
    assert definition["workflow_sha256"] == read_workflow(str(approved)).sha256
    assert definition["trigger"] == {"kind": "daily", "time": "02:30"}
    assert definition["command"][-1] == "3600" or "--timeout" in definition["command"]
    assert "--trigger" in definition["command"] and "schedule" in definition["command"]
    assert "schtasks:" in result.stdout and "command:" in result.stdout


def test_add_requires_approval_exit_6_and_calls_nothing(tmp_path, fake):
    wf = write_workflow(tmp_path / "wf.tds", synthetic_workflow())
    result = _add(tmp_path, wf)
    assert result.code == 6 and "TD-CLI-008" in result.stderr
    assert fake.calls == []
    assert not (tmp_path / "state" / "schedules").exists()


def test_print_only_creates_nothing_and_prints_xml(tmp_path, approved, fake):
    result = _add(tmp_path, approved, "--print-only")
    assert result.code == 0
    assert fake.calls == []
    assert "<Task " in result.stdout and "schtasks /Create" in result.stdout
    assert not list((tmp_path / "state" / "schedules").glob("*"))


def test_nonzero_schtasks_exit_9_includes_stderr_and_cleans_up(
    tmp_path, approved, fake
):
    fake.result = subprocess.CompletedProcess([], 1, "", "ERROR: Access is denied.")
    result = _add(tmp_path, approved)
    assert result.code == 9
    assert "Access is denied" in result.stderr and "TD-CLI-016" in result.stderr
    assert not list((tmp_path / "state" / "schedules").glob("*"))


def test_existing_name_needs_force(tmp_path, approved, fake):
    assert _add(tmp_path, approved).code == 0
    assert _add(tmp_path, approved).code == 2
    assert _add(tmp_path, approved, "--force").code == 0


def test_param_paths_are_made_absolute_and_validated(
    tmp_path, approved, fake, monkeypatch
):
    data = json.loads(approved.read_text(encoding="utf-8"))
    data["workflow_metadata"]["parameters"] = [
        {"name": "input_file", "type": "path_in", "node_id": 101, "setting": "filePath"}
    ]
    approved.write_text(json.dumps(data), encoding="utf-8")
    store_for(tmp_path / "state").add(make_entry(read_workflow(str(approved)), [], []))
    monkeypatch.chdir(tmp_path)
    result = _add(tmp_path, approved, "--param", "input_file=rel.csv")
    assert result.code == 0, result.stderr
    saved = json.loads((tmp_path / "state" / "schedules" / "nightly.json").read_text())
    assert Path(saved["params"]["input_file"]).is_absolute()
    bad = _add(tmp_path, approved, "--param", "nope=1", name="other")
    assert bad.code == 2 and "TD-CLI-005" in bad.stderr


def test_list_merges_json_and_csv(tmp_path, approved, fake):
    _add(tmp_path, approved)
    fake.by_verb["/Query"] = subprocess.CompletedProcess([], 0, FRENCH_CSV, "")
    result = call_main(["schedule", "list", "--format", "json"], env=_env(tmp_path))
    assert result.code == 0
    rows = result.json()["schedules"]
    assert [r["name"] for r in rows] == ["nightly"]
    live = rows[0]["live"]
    assert live["next_run"] == "22-10-2026 13:00:00" and live["last_result"] == 0
    text = call_main(["schedule", "list"], env=_env(tmp_path))
    assert "nightly" in text.stdout and "22-10-2026 13:00:00" in text.stdout


def test_parse_query_csv_ignores_other_tasks_and_keeps_raw_strings():
    rows = sched.parse_query_csv(FRENCH_CSV)
    assert [r["name"] for r in rows] == ["nightly", "broken"]
    assert rows[1]["last_result"] == 267011 and rows[1]["status"] == "Désactivé"
    assert sched.parse_query_csv("") == []


def test_list_survives_a_scheduler_failure(tmp_path, approved, fake):
    _add(tmp_path, approved)
    fake.by_verb["/Query"] = subprocess.CompletedProcess([], 1, "", "boom")
    result = call_main(["schedule", "list"], env=_env(tmp_path))
    assert result.code == 0 and "nightly" in result.stdout


def test_show_unknown_and_known(tmp_path, approved, fake):
    assert call_main(["schedule", "show", "ghost"], env=_env(tmp_path)).code == 2
    _add(tmp_path, approved)
    fake.by_verb["/Query"] = subprocess.CompletedProcess([], 0, FRENCH_CSV, "")
    shown = call_main(["schedule", "show", "nightly"], env=_env(tmp_path))
    assert shown.code == 0 and json.loads(shown.stdout)["live"]["status"]


def test_remove_argv_and_files_deleted(tmp_path, approved, fake):
    _add(tmp_path, approved)
    fake.calls.clear()
    result = call_main(["schedule", "remove", "nightly"], env=_env(tmp_path))
    assert result.code == 0
    assert fake.calls == [
        ["schtasks", "/Delete", "/TN", "TriggerDesigner\\nightly", "/F"]
    ]
    assert not list((tmp_path / "state" / "schedules").glob("*"))


def test_remove_missing_task_is_a_warning(tmp_path, approved, fake):
    _add(tmp_path, approved)
    fake.result = subprocess.CompletedProcess(
        [], 1, "", "ERROR: The system cannot find the file specified."
    )
    result = call_main(["schedule", "remove", "nightly"], env=_env(tmp_path))
    assert result.code == 0 and "warning" in result.stdout
    fake.result = subprocess.CompletedProcess([], 1, "", "ERROR: something else")
    assert call_main(["schedule", "remove", "x1"], env=_env(tmp_path)).code == 9


def test_non_windows_exit_9(tmp_path, approved, fake, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    for argv in (
        ["schedule", "list"],
        ["schedule", "remove", "x"],
        ["schedule", "add", "n", approved, "--daily", "01:00"],
    ):
        result = call_main(argv, env=_env(tmp_path))
        assert result.code == int(ExitCode.SCHEDULER)
        assert "Windows Task Scheduler only" in result.stderr
    assert fake.calls == []


@pytest.mark.parametrize("name", ["", "-x", "a b", "a/b", "x" * 65, "..\\evil"])
def test_name_validation(name):
    with pytest.raises(CliError):
        sched.check_name(name)


def test_name_validation_accepts_normal_names():
    for name in ("nightly", "Sales_2026-q4", "a"):
        sched.check_name(name)


def test_executable_in_development_uses_python_dash_m(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert sched.executable() == [sys.executable, "-m", "trigger_designer.cli"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert sched.executable() == [sys.executable]


@pytest.mark.parametrize(
    ("trigger", "text"),
    [
        ({"kind": "daily", "time": "02:30"}, "daily at 02:30"),
        ({"kind": "weekdays", "time": "06:00"}, "weekdays at 06:00"),
        (
            {"kind": "weekly", "days": ["MON", "THU"], "time": "06:30"},
            "weekly on MON, THU at 06:30",
        ),
        ({"kind": "hourly", "every": 1}, "every hour"),
        ({"kind": "hourly", "every": 6}, "every 6 hours"),
        ({"kind": "once", "at": "2026-11-02T06:30"}, "once at 2026-11-02 06:30"),
        ({}, "(unknown trigger)"),
    ],
)
def test_describe_trigger(trigger, text):
    assert sched.describe_trigger(trigger) == text


def test_list_text_shows_a_readable_trigger_not_a_dict(tmp_path, approved, fake):
    _add(tmp_path, approved)
    result = call_main(["schedule", "list"], env=_env(tmp_path))
    assert "daily at 02:30" in result.stdout
    assert "{" not in result.stdout and "kind" not in result.stdout
