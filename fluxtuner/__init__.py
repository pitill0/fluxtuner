"""FluxTuner package."""

from importlib.metadata import PackageNotFoundError, version

__app_name__ = "FluxTuner"

try:
    __version__ = version("fluxtuner")
except PackageNotFoundError:
    __version__ = "0.0.0"
