from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    name: str
    mode: Literal["MOCK", "SANDBOX", "PRODUCTION"]
    version: str
    capabilities: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    authentication: str


@dataclass(frozen=True)
class AdapterReceipt:
    adapter_id: str
    mode: Literal["MOCK", "SANDBOX", "PRODUCTION"]
    status: str
    accepted_fields: tuple[str, ...]
    external_reference: str


class ServiceAdapter(Protocol):
    descriptor: AdapterDescriptor

    def submit(self, *, package: dict[str, object], requested_fields: list[str],
               transfer_id: str) -> AdapterReceipt: ...
