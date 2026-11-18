"""A lazy module imports on first use, caches what it looks up, and stays out
of the way of Python's own protocols."""

import json
import sys

import pytest

from trigger_designer.core.lazy_import import LazyModule, lazy_module

#: A small stdlib module nothing else in the test run imports.
NAME = "colorsys"


@pytest.fixture(autouse=True)
def _fresh_import():
    sys.modules.pop(NAME, None)
    yield
    sys.modules.pop(NAME, None)


def test_nothing_is_imported_until_first_use():
    lazy = lazy_module(NAME)
    assert isinstance(lazy, LazyModule)
    assert NAME not in sys.modules
    assert lazy.rgb_to_hsv(1.0, 0.0, 0.0) == (0.0, 1.0, 1.0)
    assert NAME in sys.modules


def test_a_looked_up_name_is_cached_on_the_instance():
    lazy = lazy_module(NAME)
    first = lazy.rgb_to_hsv
    assert "rgb_to_hsv" in vars(lazy)  # later reads skip __getattr__
    assert lazy.rgb_to_hsv is first


def test_dunder_attributes_of_the_real_module_are_forwarded():
    assert lazy_module("json").__version__ == json.__version__


def test_a_missing_name_raises_attribute_error():
    with pytest.raises(AttributeError):
        lazy_module(NAME).no_such_function  # noqa: B018


def test_copy_and_pickle_probes_do_not_trigger_the_import():
    lazy = lazy_module(NAME)
    for protocol_name in ("__deepcopy__", "__wrapped__", "__iter__", "__len__"):
        assert not hasattr(lazy, protocol_name)
    assert NAME not in sys.modules


def test_dir_lists_the_real_module():
    assert "rgb_to_hsv" in dir(lazy_module(NAME))


def test_repr_says_whether_it_is_loaded():
    lazy = lazy_module(NAME)
    assert "not loaded" in repr(lazy)
    lazy.rgb_to_hsv  # noqa: B018
    assert "not loaded" not in repr(lazy)
