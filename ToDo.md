# Changes

- Add new node `Column OPtion` (you can think of a better name). This node will be updating column names like removing space, changing case, replacing " " with '_' etc.

## Select Node
- Add option to bulk rename like add prefix, suffix, remove all rename, reset all datatypes, remove selected rename, reset selected data types etc.
- Add option to auto set data type for all columns/ selected columns.

## Formula Node
- if there is an error in the formula then it is immidiately taking away the focus from input box, i think it is because we are clearing and re creating the config sidebar after each formula check.

## Filter Node
- Add in_between option in the filter section
- add option to add multiple filters one after other. 

## Buttons
- add better padding for buttons with text in them.

## Shift + A
- When adding new node by searching in this shift+a menu then it is adding multiple nodes after pressing enter  (th enumber dependes on how may letters were typed in the search box before first debounce)
-

## Copy paste
- getting this error
Traceback (most recent call last):
  File "C:\Projects\TriggerEditor\.venv\Lib\site-packages\nodeeditor\node_editor_window.py", line 412, in onEditPaste
    if 'nodes' not in data:
       ^^^^^^^^^^^^^^^^^^^
TypeError: argument of type 'bool' is not iterable

when pasting anything that is not a node data or a correct json!.
