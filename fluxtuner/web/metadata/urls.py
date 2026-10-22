# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Backward-compatible module alias for the protected network layer."""

import sys
from typing import TYPE_CHECKING

from fluxtuner.network import urls as _shared_module

if TYPE_CHECKING:
    from fluxtuner.network.urls import StreamTargetValidationError as StreamTargetValidationError
    from fluxtuner.network.urls import normalize_stream_target as normalize_stream_target

sys.modules[__name__] = _shared_module
