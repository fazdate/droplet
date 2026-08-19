"""Curated common-name overrides for well-known species.

The LLM's houseplant name translations are generally solid, but it can
occasionally confuse two similarly-named-but-unrelated plants — e.g. it once
translated "Arrowhead Plant" (Syngonium podophyllum) using the Hungarian term
for "Arrowroot" (Maranta arundinacea, a different plant grown for its edible
root), producing "nyílgyökér" ("arrow-root") instead of the correct
"nyíllevél" ("arrow-leaf"). On another occasion it mislabeled Monstera
deliciosa itself with "nyíllevél" (the Syngonium name above) instead of the
correct Hungarian common name, "könnyezőpálma" ("weeping palm"). This is a
small allow-list of manual corrections, keyed by a normalized scientific name
(cultivar/variety suffix stripped, lowercased), that take precedence over
whatever the LLM proposes.
"""

import re

_COMMON_NAME_OVERRIDES: dict[str, dict[str, str]] = {
    "syngonium podophyllum": {"hu": "Nyíllevél"},
    "monstera deliciosa": {"hu": "Könnyezőpálma"},
}


def _normalize_scientific_name(name: str) -> str:
    # Strip a cultivar/variety suffix, e.g. "Syngonium podophyllum 'Neon
    # Robusta'" -> "syngonium podophyllum", so cultivars of a known species
    # still get the curated name.
    base = re.split(r"['\u2018\u2019\"\u201c\u201d]", name, maxsplit=1)[0]
    return base.strip().lower()


def override_common_name(scientific_name: str, common_name: str | None, language: str) -> str | None:
    """Returns the curated common name for ``scientific_name``/``language`` if
    one is known, otherwise passes ``common_name`` through unchanged."""
    overrides = _COMMON_NAME_OVERRIDES.get(_normalize_scientific_name(scientific_name))
    if overrides and language in overrides:
        return overrides[language]
    return common_name
