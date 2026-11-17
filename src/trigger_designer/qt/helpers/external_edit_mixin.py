"""External-edit awareness for one open document (AI plan, phase 4).

When another program (an AI agent, a script) rewrites the ``.tds`` file that a
window has open, the window shows a banner with what changed. The user can look
at the changes, take them (one undo step named "External Edit", so unsaved edits
are never lost: undo brings them back) or keep their own version. Nodes the
other program added or changed carry a cue until the user marks them reviewed.

The mixin owns only the glue. The comparison is
``core.authoring.external_edit``, the file watching is
``ExternalEditWatcher``, the whole-scene replacement is
``TriggerSceneHistory.replace_scene``, and the visuals are
``ExternalEditBanner`` and ``TriggerGraphicsNode.set_external_cue``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from trigger_designer.core.authoring.external_edit import ExternalChange

#: The cue tooltip for each kind of change.
CUE_TIPS = {
    "added": "Added by an external tool. Use Mark all as reviewed when you have looked.",
    "changed": "Changed by an external tool. Use Mark all as reviewed when you have looked.",
    "connected": "Connections changed by an external tool.",
}

#: Distance of the canvas overlay buttons from the top-left corner.
OVERLAY_TOP = 10


class ExternalEditMixin:
    """Mixed into ``TriggerSubWindow``; see the module docstring."""

    # ----------------------------------------------------------------- setup
    def init_external_edit(self) -> None:
        """Create the banner (above the canvas) and the watcher. Call once,
        after the overlay buttons exist."""
        from trigger_designer.qt.helpers.external_edit_watcher import (
            ExternalEditWatcher,
        )
        from trigger_designer.qt.widgets.external_edit_banner import (
            ExternalEditBanner,
        )

        self._external_pending: ExternalChange | None = None
        self._external_cues: dict[int, str] = {}
        self._external_review_lines: tuple[str, ...] = ()
        self._external_banner = ExternalEditBanner(self)
        self._external_banner.hide()
        # ``self.layout`` is an attribute of the vendored editor widget (a
        # QVBoxLayout holding the canvas), not the ``QWidget.layout()`` method.
        self.layout.insertWidget(0, self._external_banner)
        self._external_banner.reloadRequested.connect(self.apply_external_edit)
        self._external_banner.reviewRequested.connect(self.review_external_change)
        self._external_banner.keepRequested.connect(self.keep_my_version)
        self._external_banner.reviewedRequested.connect(self.mark_external_reviewed)
        self._external_watcher = ExternalEditWatcher(self)
        self._external_watcher.changeDetected.connect(self._on_external_change)
        self._position_overlay_buttons()

    def shutdown_external_edit(self) -> None:
        """Stop watching (a Qt watcher holds a handle on the folder on Windows)."""
        watcher = getattr(self, "_external_watcher", None)
        if watcher is not None:
            watcher.stop()

    # ----------------------------------------------------- document lifecycle
    def external_edit_retarget(self) -> None:
        """The document now stands for ``self.filename`` as loaded: forget any
        earlier change and watch the file against the bytes just read."""
        if not hasattr(self, "_external_banner"):
            return  # the base class calls fileNew() before init_external_edit()
        self._reset_external_state()
        watcher = getattr(self, "_external_watcher", None)
        if watcher is not None:
            watcher.watch(self.filename, self.scene.disk_bytes)

    def external_edit_after_save(self) -> None:
        """The app wrote the file itself: its bytes are the new baseline, and a
        pending outside change is now overwritten, so its banner goes."""
        if not hasattr(self, "_external_banner"):
            return
        self._reset_external_state()
        watcher = getattr(self, "_external_watcher", None)
        if watcher is not None:
            # Retargets too: "Save as" gives the document a new file.
            watcher.watch(self.filename, self.scene.disk_bytes)

    def _reset_external_state(self) -> None:
        self._external_pending = None
        self._external_review_lines = ()
        if self._external_cues:
            self._external_cues = {}
            self.apply_external_cues()
        self._external_banner.clear()
        self._position_overlay_buttons()

    # --------------------------------------------------------------- detection
    def _on_external_change(self, change: Any) -> None:
        """The watcher saw the file change on disk (never raises into Qt)."""
        try:
            banner = self._external_banner
            if change.status == "invalid":
                self._external_pending = None
                banner.show_invalid(change.summary)
            else:
                self._external_pending = change
                banner.show_change(change, unsaved=bool(self.scene.isModified()))
            self._position_overlay_buttons()
        except Exception:  # noqa: BLE001 - a raising slot aborts the process
            logger.exception("Could not show the external change")

    # ------------------------------------------------------------------ actions
    def apply_external_edit(self) -> bool:
        """Take the outside change as ONE undo step "External Edit".

        The live state, unsaved edits included, is the step's undo target.
        Returns ``True`` when the change was applied.
        """
        try:
            return self._apply_external_edit()
        except Exception as exc:  # noqa: BLE001 - a raising slot aborts the process
            logger.exception("Could not apply the external change")
            self.logError(f"Could not apply the change made outside the app: {exc}")
            self._external_banner.show_invalid(
                "The change could not be applied; your workflow was left as it was."
            )
            self._position_overlay_buttons()
            return False

    def _apply_external_edit(self) -> bool:
        from trigger_designer.core.authoring.external_edit import analyse_external_edit

        pending = self._external_pending
        watcher = self._external_watcher
        if pending is None or not self.filename:
            return False
        if getattr(self, "_workflow_worker", None) is not None:
            self.logWarning("Wait for the run to finish, then reload the change.")
            return False
        # Re-read: the file may have changed again since the banner appeared.
        try:
            with open(self.filename, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            self._external_banner.show_invalid(f"The file cannot be read: {exc}")
            self._position_overlay_buttons()
            return False
        baseline = watcher.baseline if watcher.baseline is not None else b""
        change = analyse_external_edit(baseline, raw, self.filename)
        if change.status == "invalid" or change.data is None:
            self._external_pending = None
            self._external_banner.show_invalid(change.summary)
            self._position_overlay_buttons()
            return False

        self.commit_pending_config_edits(evaluate=False)
        was_modified = bool(self.scene.isModified())
        if not self.scene.history.replace_scene(change.data):
            return False  # a restore was already running
        self.validateConnections()
        self._drop_dock_of_removed_node()

        self.scene.disk_bytes = raw
        watcher.accept(raw)
        if not was_modified:
            # The scene now equals the file: nothing is unsaved.
            self.scene.has_been_modified = False
            self.setTitle()

        self._external_cues = dict(change.touched)
        self._external_review_lines = tuple(change.lines)
        self._external_pending = None
        self.apply_external_cues()
        self._external_banner.show_applied(len(change.touched), len(change.removed))
        self._position_overlay_buttons()
        self.logInfo(change.summary)
        return True

    def _drop_dock_of_removed_node(self) -> None:
        """A removed node must not stay in the Config Dock."""
        finder = getattr(self, "_find_config_dock", None)
        dock = finder() if callable(finder) else None
        if dock is None:
            return
        shown = dock.currentNode()
        if shown is not None and shown not in self.scene.nodes:
            dock.updateConfig([])

    def keep_my_version(self) -> None:
        """Ignore this outside change (saving later overwrites it)."""
        pending = self._external_pending
        if pending is not None:
            self._external_watcher.dismiss(pending.sha256)
        self._external_pending = None
        self._external_banner.clear()
        self._position_overlay_buttons()

    def review_external_change(self) -> None:
        """Show what changed in a list."""
        from trigger_designer.qt.widgets.external_edit_banner import (
            ExternalChangeDialog,
        )

        pending = self._external_pending
        lines = tuple(pending.lines) if pending is not None else ()
        lines = lines or self._external_review_lines
        dialog = ExternalChangeDialog(lines, self)
        dialog.exec()
        dialog.deleteLater()

    def mark_external_reviewed(self) -> None:
        """The user has looked at the changed nodes: remove the cues."""
        self._external_cues = {}
        self._external_review_lines = ()
        self.apply_external_cues()
        self._external_banner.clear()
        self._position_overlay_buttons()

    # -------------------------------------------------------------------- cues
    def apply_external_cues(self) -> None:
        """Project ``_external_cues`` onto the node graphics.

        Called after every restore (undo, redo and the apply itself): a restore
        can recreate a node's graphics, so the cue is drawn again from here and
        never stored in the file.
        """
        cues = getattr(self, "_external_cues", None)
        if cues is None:
            return
        for node in list(self.scene.nodes):
            graphics = getattr(node, "grNode", None)
            if graphics is None or not hasattr(graphics, "set_external_cue"):
                continue
            kind = cues.get(getattr(node, "id", None), "")
            if kind or getattr(graphics, "external_cue", ""):
                graphics.set_external_cue(kind, CUE_TIPS.get(kind, ""))

    # ----------------------------------------------------------------- layout
    def _position_overlay_buttons(self) -> None:
        """Keep the canvas overlay buttons below the banner while it shows.

        The buttons float at fixed positions over the canvas; a banner above
        the canvas would otherwise sit on top of them.
        """
        banner = getattr(self, "_external_banner", None)
        # ``isHidden`` (not ``isVisible``): the window may not be shown yet.
        offset = banner.height() if banner is not None and not banner.isHidden() else 0
        for name in (
            "run_button",
            "cancel_button",
            "zoom_in_button",
            "zoom_out_button",
            "fit_button",
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.move(button.x(), OVERLAY_TOP + offset)
