# TerraVia Citizen Service — Identity Resolution Specification V1

## Objective
Maintain one continuous TerraVia Person Identity without pretending that uncertain matches are proven identity.

## Matching signals
Names, birth information, authoritative identifiers, source references and other permitted attributes may produce a candidate match.

## Match states
NO_MATCH, POSSIBLE_MATCH, STRONG_MATCH, VERIFIED_MATCH, CONFLICT, HUMAN_REVIEW.

## Rules
- Never auto-merge solely from similarity.
- NID or another authoritative credential can support verification but does not replace TerraVia Person ID.
- Conflicting source records create an IdentityConflict case.
- Merge/split operations require explicit evidence and controlled authorization.
- Preserve prior identifiers and provenance after resolution.

## Resolution workflow
Candidate -> evidence collection -> source verification -> citizen review when appropriate -> authorized decision -> link/merge/split -> audit.
