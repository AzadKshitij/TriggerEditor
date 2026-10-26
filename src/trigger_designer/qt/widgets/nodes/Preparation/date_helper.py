"""Date Helper node: Qt wrapper around core/shaping/date_helper.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import date_helper as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_OP_LABELS = {op: op.replace("_", " ").capitalize() for op in core.OPS}
_TWO_DATE = {"days_between", "business_days_between"}
_ADD_OPS = {"add_days", "add_business_days"}


def _op_summary(item: dict) -> str:
    op = str(item.get("op") or "weekday_name")
    source = str(item.get("source") or "Date")
    name = str(item.get("name") or "").strip() or "Auto"
    return f"{_OP_LABELS.get(op, op)} \u00b7 {source} \u2192 {name}"


class DateHelperContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.date_helper"
    OUTPUT_KINDS = ("date_helper",)
    HISTORY = "Date Helper"
    SUMMARY = "one column per calculation"
    FORM = (
        FormSection(
            "Calendar",
            (
                Field(
                    "fiscal_start_month",
                    "Fiscal year starts",
                    "combo",
                    options=tuple(
                        (month, name) for month, name in enumerate(_MONTHS, 1)
                    ),
                ),
                Field(
                    "working_days",
                    "Working days",
                    "weekdays",
                    options=tuple((day, day[0]) for day in core.WEEKDAYS),
                    label_above=True,
                ),
                Field(
                    "_calendar_hint",
                    "Holidays, fixed date patterns and roll direction live in Advanced.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Calculations",
            (
                Field(
                    "ops",
                    "Calculation",
                    "list",
                    collapsible=True,
                    summary=_op_summary,
                    item_default={
                        "op": "weekday_name",
                        "source": "",
                        "source2": "",
                        "n": 0,
                        "n_column": "",
                        "name": "",
                    },
                    items=(
                        Field(
                            "op_name",
                            "",
                            "pair",
                            items=(
                                Field(
                                    "op",
                                    "Calculation",
                                    "combo",
                                    rebuild_on_change=True,
                                    options=tuple(
                                        (op, _OP_LABELS[op]) for op in core.OPS
                                    ),
                                ),
                                Field(
                                    "name",
                                    "Output name",
                                    "text",
                                    placeholder="Auto",
                                ),
                            ),
                        ),
                        Field("source", "Date", "column", filter="date"),
                        Field(
                            "source2",
                            "Second date",
                            "column",
                            filter="date",
                            blank=True,
                            show_if=lambda item: item.get("op") in _TWO_DATE,
                        ),
                        Field(
                            "n",
                            "Days",
                            "int",
                            minimum=-100_000,
                            maximum=100_000,
                            show_if=lambda item: item.get("op") in _ADD_OPS,
                        ),
                        Field(
                            "n_column",
                            "Days from column",
                            "column",
                            filter="numeric",
                            blank=True,
                            show_if=lambda item: item.get("op") in _ADD_OPS,
                        ),
                    ),
                ),
                Field(
                    "_calc_hint",
                    "Only fields used by the chosen calculation are shown.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Advanced date handling",
            (
                Field(
                    "date_format",
                    "Text dates",
                    "combo",
                    options=(
                        ("auto", "Auto-detect"),
                        ("%Y-%m-%d", "2024-12-31"),
                        ("%d/%m/%Y", "31/12/2024"),
                        ("%m/%d/%Y", "12/31/2024"),
                        ("%d-%b-%Y", "31-Dec-2024"),
                        ("%Y%m%d", "20241231"),
                        ("%d.%m.%Y", "31.12.2024"),
                    ),
                ),
                Field(
                    "roll",
                    "Non-working day",
                    "segment",
                    options=(
                        ("forward", "Forward"),
                        ("backward", "Backward"),
                    ),
                ),
                Field(
                    "holidays",
                    "Holidays",
                    "textarea",
                    placeholder="2024-12-25 (one per line)",
                ),
            ),
            info="Holidays, fixed date pattern and roll direction.",
            collapsible=True,
            collapsed=True,
        ),
    )


@register_node(PreparationNodes.DATE_HELPER, NodeTypes.PREPARATION)
class TriggerNode_DateHelper(ShapingNode):
    icon = "node_date_helper"
    node_code = PreparationNodes.DATE_HELPER
    node_type = NodeTypes.PREPARATION
    node_title = "Date Helper"
    content_class = DateHelperContent
    content_label_objname = "trigger_node_date_helper"
