"""Date Helper node: Qt wrapper around core/shaping/date_helper.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import date_helper as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class DateHelperContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.date_helper"
    OUTPUT_KINDS = ("date_helper",)
    HISTORY = "Date Helper"
    FORM = (
        (
            "Calendar",
            (
                Field(
                    "fiscal_start_month",
                    "Fiscal year starts",
                    "combo",
                    options=tuple(
                        (month, name)
                        for month, name in enumerate(
                            (
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
                            ),
                            1,
                        )
                    ),
                ),
                Field(
                    "working_days",
                    "Working days",
                    "choices",
                    options=tuple((day, day) for day in core.WEEKDAYS),
                ),
                Field(
                    "holidays",
                    "Holidays",
                    "textarea",
                    placeholder="2024-12-25 (one per line)",
                ),
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
                    "From a non-working day",
                    "combo",
                    options=(
                        ("forward", "Roll forward"),
                        ("backward", "Roll backward"),
                    ),
                ),
            ),
        ),
        (
            "Calculations",
            (
                Field(
                    "ops",
                    "Calculation",
                    "list",
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
                            "op",
                            "Calculation",
                            "combo",
                            options=tuple(
                                (op, op.replace("_", " ").capitalize())
                                for op in core.OPS
                            ),
                        ),
                        Field("source", "Date column", "column", filter="date"),
                        Field(
                            "source2",
                            "Second date",
                            "column",
                            filter="date",
                            blank=True,
                        ),
                        Field(
                            "n",
                            "Days",
                            "int",
                            minimum=-100_000,
                            maximum=100_000,
                        ),
                        Field(
                            "n_column",
                            "Days from column",
                            "column",
                            filter="numeric",
                            blank=True,
                        ),
                        Field("name", "Output name", "text"),
                    ),
                ),
            ),
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
