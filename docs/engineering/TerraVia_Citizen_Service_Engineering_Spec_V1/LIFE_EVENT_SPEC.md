# TerraVia Citizen Service — Life Event Specification V1

## Event lifecycle
PROPOSED -> EVIDENCE_REQUIRED -> UNDER_REVIEW -> VERIFIED -> IMPACT_ANALYSIS -> APPLIED -> HISTORICAL.
Alternative terminal states: REJECTED, DISPUTED, CANCELLED, SUPERSEDED.

## Event structure
Type, subject, occurrence time/range, evidence, source, confidence/assurance, affected domains, policy result, actions, actor, timestamps.

## Anti-cascade rule
A life event never silently changes unrelated domains. Example: marriage may update a relationship and suggest relevant service actions, but does not automatically alter surname, address, NID, passport or employer data.

## Risk
LOW, MEDIUM, HIGH, CRITICAL. High/critical events require stronger evidence and human authorization.

## Automation
AUTO only for low-risk reversible actions explicitly approved by policy. High-impact actions use MANUAL or ASSISTANCE_ONLY. STOPPED blocks automation.
