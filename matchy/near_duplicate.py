from __future__ import annotations

import hashlib

from .models import EmailCandidate
from . import scoring_core


#R055: 64-bit SimHash fingerprint over a candidate's long tokens. Each token votes per bit via a
#R055: keyed BLAKE2b digest; the sign of the per-bit vote sum sets the fingerprint bit, so
#R055: near-identical texts produce fingerprints a small Hamming distance apart.
def _simhash64(text: str) -> int:
    weights = [0] * 64
    for token in scoring_core.relevance_tokens(text):
        token_hash = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        for bit_index in range(64):
            if (token_hash >> bit_index) & 1:
                weights[bit_index] += 1
            else:
                weights[bit_index] -= 1
    fingerprint = 0
    for bit_index in range(64):
        if weights[bit_index] > 0:
            fingerprint |= 1 << bit_index
    return fingerprint


#R055: Hamming distance between two 64-bit fingerprints (count of differing bits).
def _hamming_distance(left: int, right: int) -> int:
    distance = bin(left ^ right).count("1")
    return distance


class NearDuplicateMixin:
    #R055: Resolve the near-duplicate Hamming-distance threshold. Defaults to 0 (collapsing disabled) so
    #R055: behavior is opt-in; a positive `near_duplicate_max_hamming_distance` setting enables collapsing.
    def _near_duplicate_max_distance(self) -> int:
        raw = getattr(self._settings, "near_duplicate_max_hamming_distance", 0)
        distance = 0
        try:
            parsed = int(raw)
            if parsed > 0:
                distance = parsed
        except (TypeError, ValueError):
            distance = 0
        return distance

    #R055: Collapse near-duplicate candidates (forwarded/marketing variants of the same receipt) using
    #R055: SimHash fingerprints under a Hamming-distance threshold, keeping the first representative of
    #R055: each cluster. Contentless candidates (zero fingerprint) are never collapsed since they carry
    #R055: no similarity signal. A non-positive threshold is a no-op.
    @staticmethod
    def _collapse_near_duplicates(candidates: list[EmailCandidate], max_distance: int) -> list[EmailCandidate]:
        if max_distance <= 0 or len(candidates) <= 1:
            collapsed = list(candidates)
        else:
            collapsed = []
            fingerprints: list[int] = []
            for candidate in candidates:
                fingerprint = _simhash64(f"{candidate.subject} {candidate.preview} {candidate.body_text}")
                is_duplicate = False
                if fingerprint != 0:
                    for kept_fingerprint in fingerprints:
                        if _hamming_distance(fingerprint, kept_fingerprint) <= max_distance:
                            is_duplicate = True
                if not is_duplicate:
                    collapsed.append(candidate)
                    if fingerprint != 0:
                        fingerprints.append(fingerprint)
        return collapsed
