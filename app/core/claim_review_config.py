import os

CLAIM_EDIT_VALIDATOR = os.getenv(
    "CLAIM_EDIT_VALIDATOR",
    "bart"
).lower()

if CLAIM_EDIT_VALIDATOR not in {"bart","hybrid"}:
    raise ValueError(
        "Claim edit validator must be either bart or hybrid"
    )