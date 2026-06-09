import importlib
import pkgutil


def load_cogs(app):

    loaded = []
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(app)
            loaded.append(module_info.name)
    return loaded
