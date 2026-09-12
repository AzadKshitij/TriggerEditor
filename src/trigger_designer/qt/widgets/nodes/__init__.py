import os
from os.path import dirname, join

from trigger_designer.core.node_configuration import (
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
        "module_path": "Join.Append",
        "node_code": JoinNodes.APPEND,
        "node_type": NodeTypes.JOIN,
        "node_title": "Append",
        "icon": "node_append",
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
        "node_title": "Generate Rows",
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
        "node_title": "GroupBy",
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
        "module_path": "Report.graph",
        "node_code": ReportNodes.GRAPH,
        "node_type": NodeTypes.REPORT,
        "node_title": "Graph",
        "icon": "node_graph",
    },
    {
        "module_path": "Transform.count_recors",
        "node_code": TransformNodes.COUNT_RECORDS,
        "node_type": NodeTypes.TRANSFORM,
        "node_title": "Count Records",
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
]

_LAZY_MODULE_NAMES = {
    spec["module_path"]
    for spec in _LAZY_NODE_SPECS
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
        if file.endswith(".py") and not file == "__init__.py":
            relative_path = os.path.relpath(join(root, file), base_dir)
            module_name = relative_path.replace(os.sep, ".")[:-3]
            if module_name in _LAZY_MODULE_NAMES:
                continue
            modules.append(module_name)


for module in sorted(modules):
    __import__(f"{__name__}.{module}")
