"""Deterministic local claim extractor for development and tests."""

import re

from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    ClaimStatus,
    SourceResponse,
    SupportType,
)


class RuleBasedClaimExtractor:
    """Turn bounded source sentences into explicitly unverified proposals."""

    def extract(self, source: SourceResponse) -> list[ClaimCreate]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", source.content)]
        return [
            ClaimCreate(
                statement=sentence,
                confidence=0.2,
                status=ClaimStatus.UNVERIFIED,
                source_links=[
                    ClaimSourceLink(
                        source_id=source.id,
                        support_type=SupportType.SUPPORTING,
                        strength=0.2,
                    )
                ],
            )
            for sentence in sentences[:10]
            if sentence
        ]
