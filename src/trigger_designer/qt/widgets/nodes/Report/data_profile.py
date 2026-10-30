"""Data Profile node: input unchanged on ``D``, one profile row per column on ``P``.

Logic lives in ``core/profile.py`` (engine) and ``core/shaping/data_profile.py``
(runner). This module is the Qt shell: the dock view and the background worker.

Two sources feed the dock. While you edit, it profiles the rows the canvas holds
(live evaluation passes only the first 100 rows of every input, and File Input
and the shaping nodes already trim their output, so that is all the node ever
sees). A workflow Run executes the same runner over the whole input; the node
receives that result through ``on_run_result`` and the dock then shows the
full-data profile until a setting changes or the next Run replaces it.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

import polars as pl
from qtpy.QtCore import QTimer

from trigger_designer.core.errors import translate_exception
from trigger_designer.core.frames import frame_schema
from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    register_node,
)
from trigger_designer.core.profile import (
    PROFILE_SCHEMA,
    DataProfile,
    ProfileSettings,
    profile_frame,
    profile_from_frame,
)
from trigger_designer.core.shaping import data_profile as core
from trigger_designer.core.shaping.common import as_lazy
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)
from trigger_designer.qt.widgets.profile_view import ProfileDockView


def _is_sampled(settings: dict) -> bool:
    return settings.get("sample_mode") != "full"


class DataProfileContent(ShapingContent):
    """Options form plus the profile view; one cached profile per input+settings."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.data_profile"
    OUTPUT_KINDS = ("data", "profile")
    INPUTS = 1
    HISTORY = "Profile"
    SUMMARY = "profile table"
    #: A setting change re-profiles at once; there is no pipeline to batch.
    DEFER_EVALUATION = False
    FORM = (
        FormSection(
            "Options",
            (
                Field(
                    "sample_mode",
                    "Sample",
                    "combo",
                    options=(
                        ("full", "All rows"),
                        ("head", "First N rows"),
                        ("random", "Random N rows"),
                    ),
                    hint="Which rows a workflow run profiles",
                ),
                Field(
                    "sample_rows",
                    "Rows (N)",
                    "int",
                    minimum=core.LIMITS["sample_rows"][0],
                    maximum=core.LIMITS["sample_rows"][1],
                    show_if=_is_sampled,
                    hint="How many rows to profile",
                ),
                Field(
                    "seed",
                    "Seed",
                    "int",
                    minimum=core.LIMITS["seed"][0],
                    maximum=core.LIMITS["seed"][1],
                    show_if=lambda s: s.get("sample_mode") == "random",
                    hint="The same seed picks the same random rows every run",
                ),
                Field(
                    "top_n",
                    "Top values",
                    "int",
                    minimum=core.LIMITS["top_n"][0],
                    maximum=core.LIMITS["top_n"][1],
                    hint="Most frequent values listed per column",
                ),
                Field(
                    "approx_distinct_threshold",
                    "Estimate over",
                    "int",
                    minimum=core.LIMITS["approx_distinct_threshold"][0],
                    maximum=core.LIMITS["approx_distinct_threshold"][1],
                    hint="Above this many rows, distinct counts are estimated "
                    "(within about 5%) to save time",
                ),
                Field(
                    "histogram_bins",
                    "Chart bars",
                    "int",
                    minimum=core.LIMITS["histogram_bins"][0],
                    maximum=core.LIMITS["histogram_bins"][1],
                    hint="Number of bars in a number column's distribution chart",
                ),
            ),
            collapsible=True,
            collapsed=True,
        ),
    )

    _view: ProfileDockView | None = None

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        #: The upstream frame as received (already trimmed by live evaluation).
        self.full_frame: Any = None
        self._epoch = 0
        self._lock = threading.RLock()
        #: ``(key, DataProfile)`` of the newest finished live profile.
        self._cache: tuple[tuple, DataProfile] | None = None
        self._view_generation = 0
        self._request_scheduled = False
        #: The newest Run's profile and the settings it was produced with.
        self._run_profile: DataProfile | None = None
        self._run_settings_key: tuple | None = None
        self._run_time = ""

    # ---- the Run's result --------------------------------------------------
    def on_run_result(self, variables: dict) -> None:
        """Called on the GUI thread when this node finished a workflow Run.

        The Run already profiled the whole input (the runner collects inside
        ``run_node``) and left the table in ``var_profile_<id>``; this only reads
        it back, so nothing is computed here and no thread is involved.
        """
        data = variables.get(self.output_variables[1])
        if data is None:
            return
        frame = data.collect() if isinstance(data, pl.LazyFrame) else data
        settings = self.profile_settings()
        self._run_profile = profile_from_frame(frame, settings)
        self._run_settings_key = settings.key()
        self._run_time = datetime.now().strftime("%H:%M:%S")
        self.request_profile()

    def run_profile(self) -> DataProfile | None:
        """The last Run's profile, while the settings still match it."""
        if (
            self._run_profile is not None
            and self._run_settings_key == self.profile_settings().key()
        ):
            return self._run_profile
        return None

    def dock_summary(self) -> str:
        return ""  # the "1 input - 2 outputs" line says nothing useful here

    # ---- profile cache -------------------------------------------------
    def profile_settings(self) -> ProfileSettings:
        return ProfileSettings(**core.normalize(self.settings))

    def bump_epoch(self) -> None:
        """A different upstream frame arrived: cached figures no longer apply."""
        self._epoch += 1

    def key(self) -> tuple:
        return (self._epoch, self.profile_settings().key())

    def source_frame(self) -> Any:
        return self.full_frame if self.full_frame is not None else self.frames[0]

    def current_profile(self) -> DataProfile | None:
        cached = self._cache
        return cached[1] if cached and cached[0] == self.key() else None

    def get_or_compute(self, key: tuple, frame: Any, settings: ProfileSettings):
        """Profile ``frame`` once per key; safe to call from any thread."""
        with self._lock:
            cached = self._cache
            if cached and cached[0] == key:
                return cached[1]
            profile = profile_frame(frame, settings=settings)
            if key == self.key():  # not superseded while it ran
                self._cache = (key, profile)
            return profile

    def profile_lazy(self) -> pl.LazyFrame:
        """The ``P`` socket: lazy, computed (and cached) when something collects it."""
        key, frame, settings = self.key(), self.source_frame(), self.profile_settings()
        return pl.defer(
            lambda: self.get_or_compute(key, frame, settings).to_frame(),
            schema=PROFILE_SCHEMA,
        )

    # ---- evaluation --------------------------------------------------------
    def compute(self) -> list:
        frame = self.frames[0]
        self.chips = list(core.describe([frame], self.settings))
        self.outputs = [as_lazy(frame), self.profile_lazy()]
        return self.outputs

    def on_inputs_processed(self) -> None:
        self._schedule_profile()

    def after_change(self) -> None:
        self._schedule_profile()

    def _schedule_profile(self) -> None:
        if self._view is None or self._request_scheduled:
            return
        self._request_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_profile)

    def _run_scheduled_profile(self) -> None:
        self._request_scheduled = False
        self.request_profile()

    # ---- dock ---------------------------------------------------------------
    def create_layout(self, dock_layout) -> None:
        self._view = None
        if not self.ready():
            super().create_layout(dock_layout)
            return
        view = ProfileDockView(self.node.rsm)
        view.report_title = self.node.title or "Data profile"
        view.recomputeRequested.connect(self._recompute)
        # The handler must not capture ``view``: a slot on a QObject's own
        # destroyed signal that holds the QObject keeps a wrapper alive past its
        # C++ object, which crashes inside the Qt event loop when the dock is
        # rebuilt. A plain generation number says which view went away.
        self._view_generation += 1
        generation = self._view_generation
        view.destroyed.connect(lambda *_args, g=generation: self._drop_view(g))
        self._view = view
        dock_layout.addWidget(view, 1)
        super().create_layout(dock_layout)  # the collapsed Options form
        self.request_profile()

    def _drop_view(self, generation: int) -> None:
        if generation == self._view_generation:
            self._view = None

    def _recompute(self) -> None:
        """Refresh: profile the live rows again, discarding the last Run's result."""
        self._cache = None
        self._run_profile = None
        self.bump_epoch()
        self.request_profile()

    def request_profile(self) -> None:
        view = self._view
        if view is None:
            return
        run = self.run_profile()
        if run is not None:
            try:
                view.set_profile(run, source="run", run_time=self._run_time)
            except RuntimeError:
                self._view = None
            return
        frame = self.source_frame()
        if frame is None:
            return
        try:
            columns = len(frame_schema(frame))
        except Exception:  # noqa: BLE001 - a broken plan is reported by the node
            columns = 0
        if columns > core.LIVE_MAX_COLUMNS:
            try:
                view.set_skipped(
                    f"{columns:,} columns: the live preview is skipped so the editor "
                    "stays responsive. Run the workflow to profile every column."
                )
            except RuntimeError:
                self._view = None
            return
        # Computed right here on the GUI thread: while you edit, the canvas holds
        # at most 100 rows, so this is quick, and the full-data profile comes
        # from the workflow Run instead (see on_run_result). No worker thread.
        try:
            profile = self.get_or_compute(self.key(), frame, self.profile_settings())
        except Exception as exc:  # noqa: BLE001 - shown in the dock, never raised
            try:
                view.set_failed(str(exc))
            except RuntimeError:
                self._view = None
            return
        try:
            view.set_profile(profile)
        except RuntimeError:  # the dock was rebuilt and the view deleted
            self._view = None

    # ---- persistence -----------------------------------------------------
    def deserialize(self, data, hashmap={}):  # noqa: B006
        res = super().deserialize(data, hashmap)
        # An old file has no keys; a hand-edited one may be out of range.
        self.settings = core.normalize(self.settings)
        return res


@register_node(ReportNodes.DATA_PROFILE, NodeTypes.REPORT)
class TriggerNode_DataProfile(ShapingNode):
    icon = "node_data_profile"
    node_code = ReportNodes.DATA_PROFILE
    node_type = NodeTypes.REPORT
    node_title = "Data Profile"
    content_class = DataProfileContent
    output_text = ("D", "P")
    content_label_objname = "trigger_node_data_profile"
    style = {}  # noqa: RUF012 - shared empty node style

    def _upstream_frame(self, input_values) -> Any:
        """The frame wired to input 0, before the base class samples it."""
        try:
            upstream, socket = self.getInputWithSocket(0)
        except Exception:  # noqa: BLE001 - unconnected input
            return None
        if upstream is None or socket is None or not input_values[0]:
            return None
        entry = input_values[0][socket.index]
        return entry.get("data") if entry else None

    def processInputs(self, input_values) -> list | None:
        content = self.content
        full = self._upstream_frame(input_values)
        if full is not None:
            # The profile socket is lazy, so a broken upstream plan would only
            # fail later, in the dock; read the schema here to fail on the canvas.
            try:
                frame_schema(full)
            except Exception as exc:  # noqa: BLE001 - reported on the node
                self.set_error(
                    translate_exception(exc, node=self, phase="live"), "live"
                )
                self.markDirty(True)
                self.markInvalid(True)
                return None
        if full is not content.full_frame:
            content.bump_epoch()
        content.full_frame = full
        result = super().processInputs(input_values)
        if result is not None:
            content.on_inputs_processed()
        return result
