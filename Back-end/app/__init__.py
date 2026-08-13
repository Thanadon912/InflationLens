"""Inflation calculation engine and API.

Package layout follows CALCULATION_ENGINE_GUIDELINES.md section 3.1, with one
deliberate deviation: the ``global`` package is named ``global_`` because
``global`` is a reserved Python keyword and cannot be used as a package name.
See Back-end/README.md for the full list of deliberate deviations from the
documentation.
"""

from app.factory import create_app

__all__ = ["create_app"]
