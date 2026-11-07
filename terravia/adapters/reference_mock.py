from __future__ import annotations

from .contracts import AdapterDescriptor, AdapterReceipt


class ReferenceMockAdapter:
    """A local contract fixture; it never opens a network connection."""

    descriptor = AdapterDescriptor(
        adapter_id="reference-mock-v1",
        name="TerraVia Reference Organization",
        mode="MOCK",
        version="1.0.0",
        capabilities=("qualification-review", "contact-review"),
        allowed_fields=("name", "email", "qualification"),
        authentication="LOCAL_TEST_FIXTURE",
    )

    def submit(self, *, package: dict[str, object], requested_fields: list[str], transfer_id: str) -> AdapterReceipt:
        if not requested_fields or len(set(requested_fields)) != len(requested_fields):
            raise ValueError("The adapter requires a non-empty, unique field scope.")
        if set(package) != set(requested_fields):
            raise ValueError("The package fields must match the approved field scope exactly.")
        if not set(requested_fields) <= set(self.descriptor.allowed_fields):
            raise ValueError("The reference mock adapter does not accept one or more requested fields.")
        return AdapterReceipt(
            adapter_id=self.descriptor.adapter_id,
            mode=self.descriptor.mode,
            status="MOCK_COMPLETED",
            accepted_fields=tuple(requested_fields),
            external_reference=f"mock:{transfer_id}",
        )
