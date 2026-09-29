import pytest

from PaperBee.papers.biorxiv_client import compile_query


def test_or_terms_match_phrases_ignoring_case_punctuation_and_plurals():
    matches = compile_query("[DNA language model] OR [translation efficiency]")
    assert matches("Scaling DNA-language models to whole genomes")
    assert matches("Predicting Translation Efficiency from 5' UTRs")
    assert not matches("A protein language model for stability")
    assert not matches("Modeling DNA language")


def test_terms_match_only_at_word_starts():
    matches = compile_query("[RNA]")
    assert matches("An RNA foundation model")
    assert not matches("mRNA stability")


def test_and_not_and_parentheses():
    matches = compile_query("([protein] OR [RNA]) AND [language model] AND NOT [structure]")
    assert matches("An RNA language model for translation")
    assert not matches("An RNA language model for structure prediction")
    assert not matches("A DNA language model")


def test_unsupported_syntax_is_rejected():
    with pytest.raises(ValueError):
        compile_query("[protein] NEAR [language model]")
