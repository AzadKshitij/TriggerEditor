Trigger Designer
================

TriggerEditor.exe   the editor (the window with the node canvas).
tds.exe             the command line, and the AI-tool (MCP) server.

  tds run flow.tds            run a workflow without the editor
  tds validate flow.tds       check a workflow
  tds open flow.tds           start the editor on a workflow
  tds mcp --workspace D --policy P
                              start the AI-tool server (stdio)

To use the AI-tool server, add it to your AI tool's configuration with full
paths. For example, Claude Code:

  claude mcp add trigger-designer --scope user -- "<this folder>\tds.exe" mcp --workspace "C:\audits\q3" --policy "C:\audits-policy\policy.json"

The guide is docs\mcp-server.md (if you installed the AI tool setup) or on the
project's documentation site. The program never connects to the internet.

Windows may show "unrecognised app" the first time: choose More info, then
Run anyway. These alpha builds are not code-signed yet.
