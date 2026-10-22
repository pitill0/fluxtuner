# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Backward-compatible module alias for the protected network layer."""

import sys
from typing import TYPE_CHECKING

from fluxtuner.network import transport as _shared_module

if TYPE_CHECKING:
    from fluxtuner.network.transport import ConnectedStream as ConnectedStream
    from fluxtuner.network.transport import MetadataResponseError as MetadataResponseError
    from fluxtuner.network.transport import MetadataTransportError as MetadataTransportError
    from fluxtuner.network.transport import ProtectedHTTPResponse as ProtectedHTTPResponse
    from fluxtuner.network.transport import ProtectedHTTPTransport as ProtectedHTTPTransport
    from fluxtuner.network.transport import StreamSocketFactory as StreamSocketFactory
    from fluxtuner.network.transport import SystemStreamSocketFactory as SystemStreamSocketFactory

sys.modules[__name__] = _shared_module
