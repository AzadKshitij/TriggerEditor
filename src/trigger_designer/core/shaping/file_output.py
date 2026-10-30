"""File Output: write the input to disk (Qt-free, generated code only)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy

DEFAULTS = {
    "filePath": "",
    "file_format": "csv",
    "delimiter": ",",
    "use_streaming": True,
    "include_bom": False,
    "compression": None,
}

FORMATS = (
    "csv",
    "custom_delimited",
    "excel",
    "parquet",
    "json",
    "ndjson",
    "ipc",
)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Live evaluation never writes; the sink has no output socket."""
    del frames, settings
    return []


def write_node(frames: list, settings: dict) -> None:
    """Write the input; called by generated code (Run) only."""
    settings = {**DEFAULTS, **(settings or {})}
    path = str(settings.get("filePath") or "")
    if not path:
        raise ValueError("File Output: choose an output path")
    if not frames or frames[0] is None:
        raise ValueError("File Output: no incoming data - connect an input")

    frame = as_lazy(frames[0])
    file_format = str(settings.get("file_format") or "csv")
    if file_format not in FORMATS:
        raise ValueError(f"File Output: unknown format '{file_format}'")
    delimiter = str(settings.get("delimiter") or ",")
    include_bom = bool(settings.get("include_bom", False))

    if file_format == "csv":
        options = {}
        if delimiter != ",":
            options["separator"] = delimiter
        if include_bom:
            options["include_bom"] = True
        frame.sink_csv(path, **options)
    elif file_format == "custom_delimited":
        options = {"separator": delimiter or ","}
        if include_bom:
            options["include_bom"] = True
        frame.sink_csv(path, **options)
    elif file_format == "excel":
        from trigger_designer.core.excel.frame_export import write_frame_xlsx

        write_frame_xlsx(frame, path)
    elif file_format == "parquet":
        frame.sink_parquet(path, compression="snappy")
    elif file_format == "json":
        frame.collect().write_json(path)
    elif file_format == "ndjson":
        frame.sink_ndjson(path)
    else:  # ipc
        frame.sink_ipc(path)
