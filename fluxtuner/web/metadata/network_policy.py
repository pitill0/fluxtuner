# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Backward-compatible module alias for the protected network layer."""

import sys
from typing import TYPE_CHECKING

from fluxtuner.network import network_policy as _shared_module

if TYPE_CHECKING:
    from fluxtuner.network.network_policy import (
        StreamTargetBlockedError as StreamTargetBlockedError,
    )
    from fluxtuner.network.network_policy import (
        StreamTargetResolutionError as StreamTargetResolutionError,
    )
    from fluxtuner.network.network_policy import (
        SystemStreamTargetResolver as SystemStreamTargetResolver,
    )
    from fluxtuner.network.network_policy import (
        classify_network_address as classify_network_address,
    )
    from fluxtuner.network.network_policy import (
        validate_resolved_target as validate_resolved_target,
    )

sys.modules[__name__] = _shared_module
