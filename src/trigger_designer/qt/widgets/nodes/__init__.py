import os
from os.path import dirname, join

from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    register_lazy_node,
)

_LAZY_MODULES = {
    "Report.graph": {
        "node_code": ReportNodes.GRAPH,
        "node_type": NodeTypes.REPORT,
        "node_title": "Graph",
        "icon": "node_graph",
    }
}

modules = []
base_dir = dirname(__file__)

for module_name, metadata in _LAZY_MODULES.items():
    register_lazy_node(
        metadata["node_code"],
        metadata["node_type"],
        module_path=f"{__name__}.{module_name}",
        node_title=metadata["node_title"],
        icon=metadata["icon"],
    )

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".py") and not file == "__init__.py":
            relative_path = os.path.relpath(join(root, file), base_dir)
            module_name = relative_path.replace(os.sep, ".")[:-3]
            if module_name in _LAZY_MODULES:
                continue
            modules.append(module_name)


for module in sorted(modules):
    __import__(f"{__name__}.{module}")
