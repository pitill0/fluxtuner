# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Backward-compatible alias for the remote station collection service."""

import sys

from fluxtuner.network import remote_station_collection as _shared_module

sys.modules[__name__] = _shared_module
