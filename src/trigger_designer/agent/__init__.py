"""Interfaces for external AI harnesses (see docs/plans/2026-11-13-*).

``tools`` is plain Python and always importable. ``server`` needs the optional
``agent`` extra (the MCP SDK) and is imported only by ``trigger-designer-mcp``.
"""
