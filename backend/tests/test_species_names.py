"""Tests for app.species_names.override_common_name — curated corrections for
LLM houseplant-name translations that are known to sometimes be wrong."""

from app.species_names import override_common_name


def test_should_override_known_species_translation() -> None:
    assert override_common_name("Syngonium podophyllum", "Nyílgyökér", "hu") == "Nyíllevél"


def test_should_override_cultivar_variant_of_known_species() -> None:
    assert override_common_name("Syngonium podophyllum 'Neon Robusta'", "Nyílgyökér", "hu") == "Nyíllevél"


def test_should_override_monstera_deliciosa_mislabeled_as_arrowhead() -> None:
    assert override_common_name("Monstera deliciosa", "Nyíllevél", "hu") == "Könnyezőpálma"


def test_should_pass_through_unknown_species_unchanged() -> None:
    assert override_common_name("Ficus lyrata", "Hegedűlevelű fikusz", "hu") == "Hegedűlevelű fikusz"


def test_should_pass_through_when_language_has_no_override() -> None:
    assert override_common_name("Syngonium podophyllum", "Arrowhead Plant", "en") == "Arrowhead Plant"


def test_should_pass_through_none_common_name() -> None:
    assert override_common_name("Ficus lyrata", None, "hu") is None
