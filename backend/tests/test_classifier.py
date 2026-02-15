from app.services.classifier import classify_interest, is_hot_lead


def test_classify_interest_high():
    result = classify_interest("Customer interested, shared budget and timeline, asked to schedule site visit")
    assert result == "high"


def test_classify_interest_none_for_dnc():
    result = classify_interest("Please do not call again, not interested")
    assert result == "none"


def test_is_hot_lead_requires_high_and_context():
    assert is_hot_lead("high", "Interested in 2BHK in Bandra, budget 3 crore, this month") is True
    assert is_hot_lead("medium", "Interested in Bandra, budget 3 crore") is False
