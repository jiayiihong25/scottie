from ingest.classify import CONCEPTUAL, MEMORIZATION, classify


def test_definition_heavy_text_is_memorization():
    text = (
        "Mitochondria: the organelle known as the powerhouse of the cell.\n"
        "ATP is defined as adenosine triphosphate.\n"
        "Krebs cycle: also known as the citric acid cycle.\n"
    )
    content_type, score = classify(text)
    assert content_type == MEMORIZATION
    assert score > 0.5


def test_explanatory_text_is_conceptual():
    text = (
        "Aerobic respiration produces more ATP, however it requires oxygen.\n"
        "For example, muscle cells switch to anaerobic respiration during "
        "exercise, illustrating the relationship between oxygen and energy "
        "output. This suggests a trade-off between speed and yield."
    )
    content_type, score = classify(text)
    assert content_type == CONCEPTUAL


def test_no_signal_defaults_to_conceptual():
    content_type, score = classify("The sky was a pleasant shade of blue today.")
    assert content_type == CONCEPTUAL
    assert score == 0.5


def test_near_tie_defaults_to_conceptual():
    # One hit each way is an exact tie; classify() must not tag memorization
    # on a coin flip.
    text = "This term is defined as X, however that implies Y."
    content_type, _ = classify(text)
    assert content_type == CONCEPTUAL
