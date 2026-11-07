import pytest

from terravia.adapters.reference_mock import ReferenceMockAdapter
from terravia.policy import evaluate_data_request


def test_request_policy_requires_registered_requester_and_minimum_scope():
    contract = ["name", "email", "qualification"]
    review = evaluate_data_request(requester="TerraVia Reference Organization", registered_organization="TerraVia Reference Organization",
                                  requested_fields=["name"], contract_fields=contract)
    assert review.outcome == "REVIEW"
    assert evaluate_data_request(requester="Unknown Employer", registered_organization="TerraVia Reference Organization",
                                 requested_fields=["name"], contract_fields=contract).outcome == "DENY"
    assert evaluate_data_request(requester="TerraVia Reference Organization", registered_organization="TerraVia Reference Organization",
                                 requested_fields=["name", "passport_number"], contract_fields=contract).outcome == "DENY"
    assert evaluate_data_request(requester="TerraVia Reference Organization", registered_organization="TerraVia Reference Organization",
                                 requested_fields=["name", "name"], contract_fields=contract).outcome == "DENY"


def test_mock_adapter_is_versioned_and_never_accepts_unapproved_fields():
    adapter = ReferenceMockAdapter()
    assert adapter.descriptor.mode == "MOCK"
    assert adapter.descriptor.version
    receipt = adapter.submit(package={"name": "Citizen"}, requested_fields=["name"], transfer_id="t1")
    assert receipt.mode == "MOCK"
    assert receipt.accepted_fields == ("name",)
    with pytest.raises(ValueError, match="exactly"):
        adapter.submit(package={"name": "Citizen", "email": "citizen@example.test"}, requested_fields=["name"], transfer_id="t2")
    with pytest.raises(ValueError, match="does not accept"):
        adapter.submit(package={"phone": "not-sent"}, requested_fields=["phone"], transfer_id="t3")
