# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Backward-compatible module alias for the protected network layer."""

import sys
from typing import TYPE_CHECKING

from fluxtuner.network import contracts as _shared_module

if TYPE_CHECKING:
    from fluxtuner.network.contracts import DestinationDecision as DestinationDecision
    from fluxtuner.network.contracts import MetadataFetchPolicy as MetadataFetchPolicy
    from fluxtuner.network.contracts import NetworkAddressScope as NetworkAddressScope
    from fluxtuner.network.contracts import NormalizedStreamTarget as NormalizedStreamTarget
    from fluxtuner.network.contracts import RedirectDecision as RedirectDecision
    from fluxtuner.network.contracts import ResolvedAddress as ResolvedAddress
    from fluxtuner.network.contracts import StreamTargetResolver as StreamTargetResolver

sys.modules[__name__] = _shared_module
