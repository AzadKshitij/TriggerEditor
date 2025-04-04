@echo off
@REM uv run autotyping --none-return --scalar-return --bool-param --int-param --float-param --str-param --bytes-param --guess-common-names %*
uv run autotyping --annotate-optional parent:qtpy.QtWidgets.QWidget  --aggressive  %*