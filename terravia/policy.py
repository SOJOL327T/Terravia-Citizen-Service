"""Fail-closed V1 policy decisions for service data requests."""

from dataclasses import dataclass
from typing import Literal

Outcome = Literal["ALLOW", "REVIEW", "DENY"]


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    policy_version: str = "v1"


def evaluate_data_request(*, requester: str, registered_organization: str,
                          requested_fields: list[str], contract_fields: list[str]) -> Decision:
    """A requester can reach citizen review only when org and minimum scope match."""
    if requester.strip().casefold() != registered_organization.strip().casefold():
        return Decision("DENY", "Requester does not match the service's registered organization.")
    if not requested_fields or len(set(requested_fields)) != len(requested_fields):
        return Decision("DENY", "Requested fields must be non-empty and unique.")
    if not set(requested_fields) <= set(contract_fields):
        return Decision("DENY", "Requested fields exceed the service contract's minimum scope.")
    return Decision("REVIEW", "Registered service and minimum field scope; citizen review and consent are required.")
