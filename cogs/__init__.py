"""Cog auto-loader.

A *cog* is a feature module that exposes a top-level ``register(app)`` function.
``load_cogs`` discovers every module in this package and calls its ``register``,
so adding a new feature is just: drop a new file in ``cogs/`` with a
``register(app)`` function. No central wiring to edit.
"""

import importlib
import pkgutil


def load_cogs(app):
    """Import every module in this package and call its ``register(app)``."""
    loaded = []
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(app)
            loaded.append(module_info.name)
    return loaded
