"""Load bin/hypr-rules-studio (no .py extension) as the module `studio_engine`."""
import importlib.machinery
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "bin", "hypr-rules-studio")


def load():
    if "studio_engine" in sys.modules:
        return sys.modules["studio_engine"]
    loader = importlib.machinery.SourceFileLoader("studio_engine", ENGINE)
    spec = importlib.util.spec_from_loader("studio_engine", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["studio_engine"] = module
    loader.exec_module(module)
    return module
