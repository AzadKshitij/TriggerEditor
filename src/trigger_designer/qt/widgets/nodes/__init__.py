import os
from os.path import dirname, join

from trigger_designer.core.node_configuration import (
    AuditNodes,
    IONodes,
    JoinNodes,
    NodeTypes,
    PreparationNodes,
    ReportNodes,
    TransformNodes,
    register_lazy_node,
)

_LAZY_NODE_SPECS = [
    {
        "module_path": "InOut.file_input",
        "node_code": IONodes.FILE_INPUT,
        "node_type": NodeTypes.IO,
        "node_title": "File Input",
        "icon": "node_file_input",
    },
    {
        "module_path": "InOut.file_output",
        "node_code": IONodes.FILE_OUTPUT,
        "node_type": NodeTypes.IO,
        "node_title": "File Output",
        "icon": "node_file_output",
    },
    {
        "module_path": "InOut.workpaper_output",
        "node_code": IONodes.WORKPAPER_OUTPUT,
        "node_type": NodeTypes.IO,
        "node_title": "Workpaper Output",
        "icon": "node_file_output",
    },
    {
        "module_path": "Join.Append",
        "node_code": JoinNodes.APPEND,
        "node_type": NodeTypes.JOIN,
        "node_title": "Append",
        "icon": "node_append",
    },
    {
        "module_path": "Join.union",
        "node_code": JoinNodes.UNION,
        "node_type": NodeTypes.JOIN,
        "node_title": "Union",
        "icon": "node_union",
    },
    {
        "module_path": "Join.join",
        "node_code": JoinNodes.JOIN,
        "node_type": NodeTypes.JOIN,
        "node_title": "Join",
        "icon": "node_join",
    },
    {
        "module_path": "Preparation.cleansing",
        "node_code": PreparationNodes.CLEANSING,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Cleansing",
        "icon": "node_cleanser",
    },
    {
        "module_path": "Preparation.dynamic_row_builder",
        "node_code": PreparationNodes.DYNAMIC_ROW_BUILDER,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Rows",
        "icon": "node_generate_rows",
    },
    {
        "module_path": "Preparation.filter",
        "node_code": PreparationNodes.FILTER,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Filter",
        "icon": "node_filter",
    },
    {
        "module_path": "Preparation.formula",
        "node_code": PreparationNodes.FORMULA,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Formula",
        "icon": "node_formula",
    },
    {
        "module_path": "Preparation.groupby",
        "node_code": PreparationNodes.GROUPBY,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Aggregate",
        "icon": "node_groupby",
    },
    {
        "module_path": "Preparation.select",
        "node_code": PreparationNodes.SELECT,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Select",
        "icon": "node_select",
    },
    {
        "module_path": "Preparation.sort",
        "node_code": PreparationNodes.SORT,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Sort",
        "icon": "node_sort",
    },
    {
        "module_path": "Preparation.split",
        "node_code": PreparationNodes.SPLIT,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Split",
        "icon": "node_split",
    },
    {
        "module_path": "Preparation.unique",
        "node_code": PreparationNodes.UNIQUE,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Unique",
        "icon": "node_unique",
    },
    {
        "module_path": "Preparation.normalize_columns",
        "node_code": PreparationNodes.NORMALIZE_COLUMNS,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Normalize",
        # Reuses the Select glyph until a dedicated icon ships.
        "icon": "node_select",
    },
    {
        "module_path": "Report.graph",
        "node_code": ReportNodes.GRAPH,
        "node_type": NodeTypes.REPORT,
        "node_title": "Graph",
        "icon": "node_graph",
    },
    {
        "module_path": "Report.data_profile",
        "node_code": ReportNodes.DATA_PROFILE,
        "node_type": NodeTypes.REPORT,
        "node_title": "Data Profile",
        "icon": "node_data_profile",
    },
    {
        "module_path": "Report.comment",
        "node_code": ReportNodes.COMMENT,
        "node_type": NodeTypes.REPORT,
        "node_title": "Comment",
        "icon": "node_comment",
    },
    {
        "module_path": "Transform.count_records",
        "node_code": TransformNodes.COUNT_RECORDS,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Count",
        "icon": "node_count",
    },
    {
        "module_path": "Transform.running_total",
        "node_code": TransformNodes.RUNNING_TOTAL,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Running Total",
        "icon": "node_running_total",
    },
    {
        "module_path": "Transform.transpose",
        "node_code": TransformNodes.TRANSPOSE,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Transpose",
        "icon": "node_transpose",
    },
    {
        "module_path": "Preparation.record_id",
        "node_code": PreparationNodes.RECORD_ID,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Record ID",
        "icon": "node_record_id",
    },
    {
        "module_path": "Preparation.select_records",
        "node_code": PreparationNodes.SELECT_RECORDS,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Select Records",
        "icon": "node_select_records",
    },
    {
        "module_path": "Preparation.find_replace",
        "node_code": PreparationNodes.FIND_REPLACE,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Find and Replace",
        "icon": "node_find_replace",
    },
    {
        "module_path": "Preparation.date_helper",
        "node_code": PreparationNodes.DATE_HELPER,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Date Helper",
        "icon": "node_date_helper",
    },
    {
        "module_path": "Preparation.multi_field_formula",
        "node_code": PreparationNodes.MULTI_FIELD_FORMULA,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Multi-Field Formula",
        "icon": "node_multi_field_formula",
    },
    {
        "module_path": "Preparation.text_to_columns",
        "node_code": PreparationNodes.TEXT_TO_COLUMNS,
        "node_type": NodeTypes.PREPARATION,
        "node_title": "Text to Columns",
        "icon": "node_text_to_columns",
    },
    {
        "module_path": "Transform.pivot",
        "node_code": TransformNodes.PIVOT,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Pivot",
        "icon": "node_pivot",
    },
    {
        "module_path": "Transform.unpivot",
        "node_code": TransformNodes.UNPIVOT,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Unpivot",
        "icon": "node_unpivot",
    },
    {
        "module_path": "Transform.window",
        "node_code": TransformNodes.WINDOW,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Window",
        "icon": "node_window",
    },
    {
        "module_path": "Transform.sql_query",
        "node_code": TransformNodes.SQL_QUERY,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "SQL Query",
        "icon": "node_sql_query",
    },
    {
        "module_path": "Join.reconcile",
        "node_code": JoinNodes.RECONCILE,
        "node_type": NodeTypes.JOIN,
        "node_title": "Reconcile",
        "icon": "node_reconcile",
    },
    {
        "module_path": "Join.fuzzy_match",
        "node_code": JoinNodes.FUZZY_MATCH,
        "node_type": NodeTypes.JOIN,
        "node_title": "Fuzzy Match",
        "icon": "node_fuzzy_match",
    },
    {
        "module_path": "Audit.benford",
        "node_code": AuditNodes.BENFORD,
        "node_type": NodeTypes.AUDIT,
        "node_title": "Benford",
        "icon": "node_benford",
    },
    {
        "module_path": "Audit.gaps",
        "node_code": AuditNodes.GAPS,
        "node_type": NodeTypes.AUDIT,
        "node_title": "Gaps",
        "icon": "node_gaps",
    },
    {
        "module_path": "Audit.duplicates",
        "node_code": AuditNodes.DUPLICATES,
        "node_type": NodeTypes.AUDIT,
        "node_title": "Duplicates",
        "icon": "node_duplicates",
    },
    {
        "module_path": "Audit.risk_filters",
        "node_code": AuditNodes.RISK_FILTERS,
        "node_type": NodeTypes.AUDIT,
        "node_title": "Risk Filters",
        "icon": "node_risk_filters",
    },
    {
        "module_path": "Audit.sample",
        "node_code": AuditNodes.SAMPLE,
        "node_type": NodeTypes.AUDIT,
        "node_title": "Sample",
        "icon": "node_sample",
    },
]

_LAZY_MODULE_NAMES = {spec["module_path"] for spec in _LAZY_NODE_SPECS}

#: Helper modules under ``nodes/`` that are not nodes. The sweep below would
#: import them at startup, pulling matplotlib and the Qt canvas into every
#: launch; they load with the node that needs them instead. ``chart_renderer``
#: is the shared contract and ``pyqtgraph_view`` the opt-in renderer: neither
#: belongs to a node, and neither may drag a plotting library into startup.
_LAZY_HELPER_MODULES = {
    "Audit._base",
    "Audit.benford_chart",
    "Report.chart_renderer",
    "Report.chart_view",
    "Report.chart_window",
    "Report.pyqtgraph_view",
}

modules = []
base_dir = dirname(__file__)

for spec in _LAZY_NODE_SPECS:
    register_lazy_node(
        spec["node_code"],
        spec["node_type"],
        module_path=f"{__name__}.{spec['module_path']}",
        node_title=spec["node_title"],
        icon=spec["icon"],
    )

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".py") and file != "__init__.py":
            relative_path = os.path.relpath(join(root, file), base_dir)
            module_name = relative_path.replace(os.sep, ".")[:-3]
            if module_name in _LAZY_MODULE_NAMES:
                continue
            if module_name in _LAZY_HELPER_MODULES:
                continue
            modules.append(module_name)


for module in sorted(modules):
    __import__(f"{__name__}.{module}")
