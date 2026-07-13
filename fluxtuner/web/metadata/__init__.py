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

__all__ = [
    "DestinationDecision",
    "MetadataFetchPolicy",
    "NetworkAddressScope",
    "NormalizedStreamTarget",
    "RedirectDecision",
    "ResolvedAddress",
    "StreamTargetResolver",
]
