# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Contracts for the FluxTuner Web metadata subsystem."""

from .contracts import (
    DestinationDecision,
    MetadataFetchPolicy,
    NetworkAddressScope,
    NormalizedStreamTarget,
    RedirectDecision,
    ResolvedAddress,
    StreamTargetResolver,
)
from .network_policy import (
    StreamTargetBlockedError,
    StreamTargetResolutionError,
    SystemStreamTargetResolver,
    classify_network_address,
    validate_resolved_target,
)
from .urls import StreamTargetValidationError, normalize_stream_target

__all__ = [
    "DestinationDecision",
    "MetadataFetchPolicy",
    "NetworkAddressScope",
    "NormalizedStreamTarget",
    "RedirectDecision",
    "ResolvedAddress",
    "StreamTargetResolver",
    "StreamTargetBlockedError",
    "StreamTargetResolutionError",
    "StreamTargetValidationError",
    "SystemStreamTargetResolver",
    "classify_network_address",
    "normalize_stream_target",
    "validate_resolved_target",
]
