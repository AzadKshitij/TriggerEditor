"""Plain-language error model, catalogue and translator.

Qt-free: plans 02, 03 and 08 import from here without pulling in widgets.
"""

from trigger_designer.core.errors.attribution import Ancestor, attribute_upstream
from trigger_designer.core.errors.builders import make_error
from trigger_designer.core.errors.catalogue import CATALOGUE, render_entry
from trigger_designer.core.errors.enrich import (
    EnrichJob,
    EnrichResult,
    enrich_error,
    enrich_sync,
)
from trigger_designer.core.errors.locator import (
    LocateResult,
    locate_conversion_failures,
)
from trigger_designer.core.errors.model import (
    KNOCK_ON_CODES,
    ErrorContext,
    NodeError,
    SuggestedFix,
    normalise_path,
    shorten,
)
from trigger_designer.core.errors.translator import (
    translate_exception,
    translate_sql_diagnostic,
)

__all__ = [
    "CATALOGUE",
    "KNOCK_ON_CODES",
    "Ancestor",
    "EnrichJob",
    "EnrichResult",
    "ErrorContext",
    "LocateResult",
    "NodeError",
    "SuggestedFix",
    "attribute_upstream",
    "enrich_error",
    "enrich_sync",
    "locate_conversion_failures",
    "make_error",
    "normalise_path",
    "render_entry",
    "shorten",
    "translate_exception",
    "translate_sql_diagnostic",
]
