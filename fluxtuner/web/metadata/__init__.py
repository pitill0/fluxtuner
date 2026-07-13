# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Contracts for the FluxTuner Web metadata subsystem."""

from .client import MetadataRedirectError, fetch_protected_stream_metadata
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
from .transport import (
    MetadataResponseError,
    MetadataTransportError,
    ProtectedHTTPTransport,
    SystemStreamSocketFactory,
)
from .urls import StreamTargetValidationError, normalize_stream_target

__all__ = [
    "DestinationDecision",
    "MetadataFetchPolicy",
    "MetadataRedirectError",
    "MetadataResponseError",
    "MetadataTransportError",
    "NetworkAddressScope",
    "NormalizedStreamTarget",
    "RedirectDecision",
    "ResolvedAddress",
    "StreamTargetResolver",
    "StreamTargetBlockedError",
    "StreamTargetResolutionError",
    "StreamTargetValidationError",
    "SystemStreamSocketFactory",
    "SystemStreamTargetResolver",
    "ProtectedHTTPTransport",
    "classify_network_address",
    "fetch_protected_stream_metadata",
    "normalize_stream_target",
    "validate_resolved_target",
]
