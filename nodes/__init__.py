import os
from os.path import dirname, basename, isfile, join

modules = []
base_dir = dirname(__file__)

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".py") and not file == "__init__.py":
            relative_path = os.path.relpath(join(root, file), base_dir)
            module_name = relative_path.replace(os.sep, ".")[:-3]
            modules.append(module_name)


for module in modules:
    __import__(f"{__name__}.{module}")
