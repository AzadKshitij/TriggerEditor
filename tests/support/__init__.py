"""Reusable helpers shared by the unit, UI and E2E layers.

Import from the specific module, for example::

    from tests.support.frames import assert_frames_match
    from tests.support.workflows import WorkflowCase, materialize

Keeping these here instead of in each test file means one builder has one
behaviour, and a change to the app only has to be followed in one place.
"""
