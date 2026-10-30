"""The generated-code policy: attack table, benign table, future nodes (plan 08 6.3)."""

from __future__ import annotations

import pytest

from trigger_designer.core.headless.code_policy import (
    CodePolicyError,
    make_safe_builtins,
    sandbox_code_filter,
    sandbox_globals,
    validate_generated_code,
)

IO = ["C:/data/in.csv", "C:/data/.out.tdtmp-ab12cd34.csv"]

ATTACKS = [
    ("M01", "x = __import__('os').system('calc')", "not allowed"),
    ("M02", "import subprocess\nsubprocess.run(['calc'])", "import of 'subprocess'"),
    ("M03", "import os\nos.system('calc')", ".system"),
    ("M04", "open('C:/Windows/win.ini').read()", "name 'open'"),
    ("M05", "eval('1+1')", "name 'eval'"),
    ("M06", "exec('import os')", "name 'exec'"),
    ("M07", "getattr(pl, 'os')", "name 'getattr'"),
    ("M08", "().__class__.__bases__[0].__subclasses__()", "not allowed"),
    ("M09", "(lambda: 0).__globals__", "__globals__"),
    ("M10", "pl.scan_csv('C:/Users/victim/secrets.csv')", "undeclared path"),
    (
        "M11",
        "pl.DataFrame({'a':[1]}).write_csv('C:/Users/victim/Startup/x.csv')",
        "undeclared path",
    ),
    ("M12", "p = 'C:/data/' + 'in.csv'\npl.scan_csv(p)", "needs a literal file path"),
    ("M13", "d.execute(\"COPY (SELECT 1) TO 'C:/x.csv'\")", "only SELECT/WITH"),
    ("M14", "d.execute(\"SELECT * FROM read_csv('C:/secret.csv')\")", "read_csv"),
    ("M15", "d.execute(\"ATTACH 'x.db'\")", "only SELECT/WITH"),
    ("M16", "duckdb.connect('C:/x.db')", "':memory:'"),
    ("M17", "d.execute('SELECT 1; DROP TABLE t')", "multiple SQL statements"),
    ("M18", "q = 'SEL' + 'ECT 1'\nd.execute(q)", "string literal"),
    ("M19", "class A: pass", "ClassDef"),
    ("M20", "with open('x') as f: pass", "With is not allowed"),
    ("M21", "def f():\n    global x", "Global"),
    ("M22", "import requests", "import of 'requests'"),
    ("M23", "from os import system", "from os import"),
    ("M24", "pl.plugins.register_plugin_function(1)", "not allowed"),
    ("M25", "pl.col('a').map_elements(lambda v: open('x').read())", "name 'open'"),
    ("M26", "x = (y := breakpoint())", "NamedExpr"),
    ("M27", "@f\ndef g(): pass", "decorators"),
    ("M28", "import os\nos.environ['PATH']", ".environ"),
    ("M29", "os.path.unlink('x')", ".unlink"),
    ("M30", "x = (", "syntax error"),
    ("M31", "pl.read_database('select 1', 'sqlite:///x.db')", ""),
    ("M32", "async def f(): pass", "AsyncFunctionDef"),
]


@pytest.mark.parametrize("ident,code,needle", ATTACKS, ids=[a[0] for a in ATTACKS])
def test_attack_table(ident, code, needle):
    with pytest.raises(CodePolicyError) as exc:
        validate_generated_code(code, io_paths=IO)
    assert needle in exc.value.reason


BENIGN = [
    "pl.scan_csv('C:\\\\data\\\\in.csv', infer_schema=False)",
    "pl.LazyFrame().sink_csv('C:/data/.out.tdtmp-ab12cd34.csv')",
    "d.execute('WITH a AS (SELECT 1 AS \"set\") SELECT * FROM a').pl()",
    "x = 1\ndel x",
    (
        "def _ensure_lazyframe(d):\n"
        "    if isinstance(d, pl.LazyFrame):\n"
        "        return d\n"
        "    raise TypeError(f'bad {type(d)}')\n"
    ),
    "os.path.basename('C:/data/in.csv')",
    "d.execute(\"SELECT 'don''t; copy' AS x\")",
]


@pytest.mark.parametrize("code", BENIGN)
def test_benign_table(code):
    validate_generated_code(code, io_paths=IO)


FUTURE = [
    "from trigger_designer.core.input_source import build_source\n"
    "df = build_source({'filePath': 'C:/data/in.csv'})",
    "from trigger_designer.core.audit.duplicates import DuplicatesParams, run_duplicates\n",
    "from trigger_designer.core.audit.gaps import GapsParams, run_gaps\n",
    "from trigger_designer.core.audit.benford import BenfordParams, run_benford\n",
    "from trigger_designer.core.audit.sampling import SamplingParams, run_sample\n",
    "from trigger_designer.core.audit.risk_filters import RiskParams, run_risk_filters\n",
    "from trigger_designer.core.profile import profile_table, empty_profile_frame\n",
    "from trigger_designer.core.excel.frame_export import write_frame_xlsx\n"
    "write_frame_xlsx(df, 'C:/data/.out.tdtmp-ab12cd34.csv')",
    "from trigger_designer.core.workpaper.node_runner import run_workpaper\n",
    "import json\nfrom trigger_designer.core.shaping.window import run_node as _run_node\n"
    "_run_node([df], json.loads('{\"a\": 1}'))",
    "import json\nfrom trigger_designer.core.shaping.file_output import write_node as _w\n"
    '_w([df], json.loads(\'{"filePath": "C:/data/.out.tdtmp-ab12cd34.csv"}\'))',
    "from datetime import datetime, timedelta\nimport os",
]


@pytest.mark.parametrize("code", FUTURE)
def test_future_node_imports_pass(code):
    validate_generated_code(code, io_paths=IO)


TAMPERED = [
    "d = {'filePath': 'C:/elsewhere/x.csv'}",
    "d = {'output_path': 'C:/elsewhere/x.xlsx'}",
    'import json\njson.loads(\'{"filePath": "C:/elsewhere/x.csv"}\')',
    "from trigger_designer.core.shaping.Evil import run_node",
    "from trigger_designer.core.input_source import open_anything",
    "from trigger_designer.core.excel.frame_export import write_frame_xlsx\n"
    "write_frame_xlsx(df, 'C:/elsewhere/x.xlsx')",
    "from json import loads",
    "import datetime",
]


@pytest.mark.parametrize("code", TAMPERED)
def test_tampered_helper_code_is_refused(code):
    with pytest.raises(CodePolicyError):
        validate_generated_code(code, io_paths=IO)


def test_undeclared_path_refused_declared_allowed():
    code = "pl.scan_csv('C:/data/in.csv')"
    validate_generated_code(code, io_paths=IO)
    with pytest.raises(CodePolicyError):
        validate_generated_code(code, io_paths=["C:/other/x.csv"])
    validate_generated_code(code, io_paths=None)


def test_path_comparison_is_case_and_slash_insensitive_on_windows():
    import os

    if os.name != "nt":
        pytest.skip("Windows path normalisation")
    validate_generated_code("pl.scan_csv('c:\\\\DATA\\\\IN.csv')", io_paths=IO)


def test_dunder_and_unicode_obfuscation():
    for code in ("x = ().__class__", "y = [].__len__", "getattr\u200b = 1\nopen('x')"):
        with pytest.raises(CodePolicyError):
            validate_generated_code(code, io_paths=IO)


def test_sandbox_globals_contract():
    g = sandbox_globals()
    builtins = g["__builtins__"]
    for name in ("open", "eval", "exec", "getattr", "compile", "input", "globals"):
        assert name not in builtins
    assert "__import__" in builtins
    assert not hasattr(g["os"], "system")
    assert set(vars(g["os"].path)) >= {"join", "basename", "exists"}
    assert "open" not in make_safe_builtins()


def test_import_statements_are_stripped_only_for_os():
    out = sandbox_code_filter("import os\nx = os.path.basename('a/b')\n", io_paths=IO)
    assert "import" not in out
    out = sandbox_code_filter("import polars as pl\nx = 1\n", io_paths=IO)
    assert "import polars" in out


def test_policy_error_marks_violation_for_the_executor():
    assert CodePolicyError.policy_violation is True


def test_executor_marks_policy_violation_and_default_filter_is_inert():
    from trigger_designer.core.ExecutionCheck.executor import NodeExecutor

    class FakeNode:
        content = None

        def __init__(self, code):
            self._code = code

        def get_code(self):
            return self._code

    ex = NodeExecutor()
    ex.code_filter = lambda code: sandbox_code_filter(code, IO)
    bad = ex.execute_node(FakeNode("open('x')"))
    assert bad.success is False and bad.policy_violation is True
    good = NodeExecutor().execute_node(FakeNode("y = 1 + 1"))
    assert (
        good.success is True and good.variables["y"] == 2 and not good.policy_violation
    )
