"""Static policy for generated code run by the command line (plan 08 3.11, S4).

A ``.tds`` can come from anyone and the nodes' ``get_code()`` output is
``exec()``'d. This module is defence in depth against accidental or casual
abuse (a tampered path, a crafted setting): it parses the code, allows only
the AST shapes and imports generated code uses, forbids dunder and file/OS
APIs, and requires every file path to be one the approved workflow declared.
It is not an OS sandbox; hostile files stay unapproved.

Qt-free; polars and duckdb are imported only inside :func:`sandbox_globals`.
"""

from __future__ import annotations

import ast
import builtins as _b
import json
import os
import re
import types
from collections.abc import Collection

#: module -> None (bare ``import m`` allowed) or the set of names ``from m
#: import ...`` may take. THE table future nodes extend (plan 08 3.11).
GENERATED_IMPORTS: dict[str, set[str] | None] = {
    "polars": None,
    "duckdb": None,
    "fastexcel": None,
    "os": None,
    "json": None,
    "datetime": {"datetime", "timedelta"},
    "trigger_designer.core.utils.dtype_utils": {"normalize_to_supported_dtypes"},
    "trigger_designer.core.utils.cleansing_util": {"DataCleansing", "NullStrategy"},
    "trigger_designer.core.input_source": {"build_source", "name_blank_columns"},
    "trigger_designer.core.audit.duplicates": {"DuplicatesParams", "run_duplicates"},
    "trigger_designer.core.audit.gaps": {"GapsParams", "run_gaps"},
    "trigger_designer.core.audit.benford": {"BenfordParams", "run_benford"},
    "trigger_designer.core.audit.sampling": {"SamplingParams", "run_sample"},
    "trigger_designer.core.audit.risk_filters": {"RiskParams", "run_risk_filters"},
    "trigger_designer.core.profile": {"profile_table", "empty_profile_frame"},
    "trigger_designer.core.excel.frame_export": {"write_frame_xlsx"},
    "trigger_designer.core.workpaper.node_runner": {"run_workpaper"},
}
#: module prefix -> names (module part must match ``[a-z_]+``).
GENERATED_IMPORT_PREFIXES: dict[str, set[str]] = {
    "trigger_designer.core.shaping.": {"run_node", "write_node"},
}
PATH_KEYS = frozenset({"filePath", "output_path", "db_path"})

ALLOWED_NODE_TYPES = {
    ast.Module,
    ast.alias,
    ast.Expr,
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.Import,
    ast.ImportFrom,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.If,
    ast.While,
    ast.For,
    ast.Try,
    ast.ExceptHandler,
    ast.Raise,
    ast.Pass,
    ast.Break,
    ast.Continue,
    ast.Delete,
    ast.Del,
    ast.Call,
    ast.keyword,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Lambda,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Starred,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.Invert,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
}
OS_PATH_OK = frozenset(
    {
        "basename",
        "dirname",
        "join",
        "splitext",
        "exists",
        "isfile",
        "isdir",
        "abspath",
        "normpath",
        "sep",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "memoryview",
        "exit",
        "quit",
        "help",
        "dir",
        "super",
        "classmethod",
        "staticmethod",
        "property",
        "__builtins__",
        "sys",
        "subprocess",
        "importlib",
        "builtins",
        "ctypes",
        "socket",
        "shutil",
        "pathlib",
        "pickle",
        "marshal",
        "io",
        "tempfile",
        "glob",
        "requests",
        "urllib",
    }
)
FORBIDDEN_ATTRS = frozenset(
    {
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnv",
        "execv",
        "execl",
        "startfile",
        "unlink",
        "rmdir",
        "removedirs",
        "makedirs",
        "mkdir",
        "chmod",
        "chown",
        "environ",
        "putenv",
        "getenv",
        "listdir",
        "scandir",
        "walk",
        "kill",
        "fork",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "os",
        "sys",
        "subprocess",
        "importlib",
        "builtins",
        "modules",
        "f_globals",
        "f_locals",
        "gi_frame",
        "cr_frame",
        "tb_frame",
        "mro",
        "load_extension",
        "install_extension",
        "plugins",
        "register_plugin_function",
        "read_database",
        "read_database_uri",
        "write_database",
        "read_clipboard",
        "write_clipboard",
        "from_pandas",
        "to_pandas",
        "register_filesystem",
        "scan_pyarrow_dataset",
        "scan_delta",
        "scan_iceberg",
        "read_delta",
        "write_delta",
    }
)
IO_PREFIXES = ("scan_", "read_", "sink_", "write_")
IO_KWARGS = ("source", "file", "path", "f", "workbook")
SQL_CALLS = frozenset({"execute", "sql", "query", "executemany"})
SQL_FORBIDDEN_RE = re.compile(
    r"\b(read_\w+|\w+_scan|glob|copy|attach|detach|install|load|pragma|export|import|"
    r"call|create|drop|insert|update|delete|alter|getenv|current_setting|http\w*|s3|"
    r"sniff_csv|duckdb_\w+|pg_\w+|write_\w+|force|checkpoint|vacuum)\b",
    re.IGNORECASE,
)
_SQL_LIT = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")


class CodePolicyError(Exception):
    """Generated code was refused. ``policy_violation`` marks it for the executor."""

    policy_violation = True

    def __init__(self, reason: str, lineno: int | None = None) -> None:
        super().__init__(reason if lineno is None else f"line {lineno}: {reason}")
        self.reason = reason
        self.lineno = lineno


def norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _import_names(module: str) -> set[str] | None:
    names = GENERATED_IMPORTS.get(module)
    if names is not None:
        return names
    for prefix, allowed in GENERATED_IMPORT_PREFIXES.items():
        if module.startswith(prefix) and re.fullmatch(
            r"[a-z_]+", module[len(prefix) :]
        ):
            return allowed
    return None


def validate_generated_code(
    code: str, *, io_paths: Collection[str] | None = None
) -> None:
    """Raise :class:`CodePolicyError` unless ``code`` is acceptable.

    ``io_paths`` are the only files the code may name; ``None`` skips the path
    rules (used when checking code in isolation).
    """
    allowed = None if io_paths is None else {norm_path(p) for p in io_paths}
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodePolicyError(f"syntax error: {exc.msg}", exc.lineno) from None
    _scan_path_keys(tree, allowed)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if type(node) not in ALLOWED_NODE_TYPES:
            raise CodePolicyError(f"{type(node).__name__} is not allowed", line)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name not in GENERATED_IMPORTS
                    or GENERATED_IMPORTS[alias.name] is not None
                ):
                    raise CodePolicyError(
                        f"import of '{alias.name}' is not allowed", line
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = _import_names(module) if not node.level else None
            if not names or any(alias.name not in names for alias in node.names):
                raise CodePolicyError(
                    f"'from {module} import ...' is not allowed", line
                )
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or (
                node.id.startswith("__") and node.id != "__name__"
            ):
                raise CodePolicyError(f"name '{node.id}' is not allowed", line)
        elif isinstance(node, ast.Delete):
            if any(not isinstance(t, ast.Name) for t in node.targets):
                raise CodePolicyError("del is only allowed on plain names", line)
        elif isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                raise CodePolicyError("decorators are not allowed", line)
        elif isinstance(node, ast.Attribute):
            _check_attribute(node, line)
        elif isinstance(node, ast.Call):
            _check_call(node, line, allowed)


def _check_attribute(node: ast.Attribute, line: int | None) -> None:
    if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRS:
        raise CodePolicyError(f"attribute '.{node.attr}' is not allowed", line)
    value = node.value
    if isinstance(value, ast.Name) and value.id == "os" and node.attr != "path":
        raise CodePolicyError(f"'os.{node.attr}' is not allowed (only os.path.*)", line)
    if (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "os"
        and value.attr == "path"
        and node.attr not in OS_PATH_OK
    ):
        raise CodePolicyError(f"'os.path.{node.attr}' is not allowed", line)


def _literal_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _check_call(node: ast.Call, line: int | None, allowed: set[str] | None) -> None:
    func = node.func
    attr = func.attr if isinstance(func, ast.Attribute) else None
    if attr in SQL_CALLS:
        sql = _literal_str(node.args[0]) if node.args else None
        if sql is None:
            raise CodePolicyError("SQL must be a string literal", line)
        _check_sql(sql, line)
    if (
        attr == "connect"
        and isinstance(func.value, ast.Name)
        and func.value.id == "duckdb"
        and (
            not node.args
            or _literal_str(node.args[0]) != ":memory:"
            or len(node.args) > 1
            or node.keywords
        )
    ):
        raise CodePolicyError("duckdb.connect only accepts ':memory:'", line)
    if attr and attr.startswith(IO_PREFIXES):
        target = (
            node.args[0]
            if node.args
            else next((k.value for k in node.keywords if k.arg in IO_KWARGS), None)
        )
        path = _literal_str(target)
        if path is None:
            raise CodePolicyError(f"'{attr}' needs a literal file path", line)
        if allowed is not None and norm_path(path) not in allowed:
            raise CodePolicyError(f"'{attr}' touches an undeclared path", line)
    if isinstance(func, ast.Name) and func.id.startswith("write_"):
        for arg in node.args[:2]:
            literal = _literal_str(arg)
            if (
                literal is not None
                and allowed is not None
                and norm_path(literal) not in allowed
            ):
                raise CodePolicyError(f"'{func.id}' touches an undeclared path", line)


def _scan_path_keys(tree: ast.AST, allowed: set[str] | None) -> None:
    """Every value under a ``PATH_KEYS`` key, in dict literals and in JSON-looking
    string constants, must be a declared path."""
    if allowed is None:
        return

    def check(key, value, line):
        if (
            key in PATH_KEYS
            and isinstance(value, str)
            and value
            and norm_path(value) not in allowed
        ):
            raise CodePolicyError(f"'{key}' value is not a declared path", line)

    def walk_json(obj, line):
        if isinstance(obj, dict):
            for key, value in obj.items():
                check(key, value, line)
                walk_json(value, line)
        elif isinstance(obj, list):
            for value in obj:
                walk_json(value, line)

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=False):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    check(key.value, value.value, line)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.lstrip()[:1] in ("{", "[")
        ):
            try:
                walk_json(json.loads(node.value), line)
            except ValueError:
                continue


def _check_sql(sql: str, line: int | None) -> None:
    stripped = sql.strip().rstrip(";").strip()
    bare = _SQL_LIT.sub("''", stripped)
    if ";" in bare:
        raise CodePolicyError("multiple SQL statements are not allowed", line)
    if not re.match(r"(?is)^(select|with)\b", stripped):
        raise CodePolicyError("only SELECT/WITH SQL is allowed", line)
    match = SQL_FORBIDDEN_RE.search(bare)
    if match:
        raise CodePolicyError(f"SQL token '{match.group(0)}' is not allowed", line)


SAFE_BUILTIN_NAMES = [
    "abs",
    "all",
    "any",
    "bool",
    "bytes",
    "callable",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "hasattr",
    "hash",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "print",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "type",
    "zip",
    "None",
    "True",
    "False",
    "Ellipsis",
    "NotImplemented",
    "Exception",
    "BaseException",
    "ArithmeticError",
    "AttributeError",
    "KeyError",
    "IndexError",
    "LookupError",
    "NameError",
    "OSError",
    "FileNotFoundError",
    "PermissionError",
    "RuntimeError",
    "StopIteration",
    "TypeError",
    "ValueError",
    "ZeroDivisionError",
    "UnicodeDecodeError",
    "UnicodeEncodeError",
    "AssertionError",
    "NotImplementedError",
    "OverflowError",
]


def make_safe_builtins() -> dict:
    namespace = {n: getattr(_b, n) for n in SAFE_BUILTIN_NAMES if hasattr(_b, n)}
    # DuckDB's ``.pl()`` imports polars through the calling frame's builtins
    # (plan 08 X6); the validator forbids the *name* so generated code cannot
    # reach it.
    namespace["__import__"] = _b.__import__
    return namespace


def make_safe_os() -> types.SimpleNamespace:
    path = types.SimpleNamespace(
        **{n: getattr(os.path, n) for n in OS_PATH_OK if n != "sep"}, sep=os.sep
    )
    return types.SimpleNamespace(path=path, sep=os.sep)


class _StripOsImport(ast.NodeTransformer):
    """``import os`` becomes ``pass``: the exec globals already hold SafeOs."""

    def visit_Import(self, node: ast.Import):
        node.names = [a for a in node.names if a.name != "os"]
        return node if node.names else ast.copy_location(ast.Pass(), node)


def sandbox_code_filter(code: str, io_paths: Collection[str] | None = None) -> str:
    """The executor's ``code_filter``: validate, then drop ``import os``."""
    validate_generated_code(code, io_paths=io_paths)
    tree = _StripOsImport().visit(ast.parse(code))
    return ast.unparse(ast.fix_missing_locations(tree))


def sandbox_globals() -> dict:
    """Execution globals for generated code (restricted builtins, safe ``os``)."""
    import datetime as dt

    import duckdb
    import fastexcel
    import polars as pl

    from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
    from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

    return {
        "__builtins__": make_safe_builtins(),
        "pl": pl,
        "duckdb": duckdb,
        "fastexcel": fastexcel,
        "os": make_safe_os(),
        "datetime": dt.datetime,
        "timedelta": dt.timedelta,
        "normalize_to_supported_dtypes": normalize_to_supported_dtypes,
        "DataCleansing": DataCleansing,
        "NullStrategy": NullStrategy,
    }
