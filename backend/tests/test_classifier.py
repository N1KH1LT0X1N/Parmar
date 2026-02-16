from app.services.classifier import classify_interest, is_hot_lead


# ---------- classify_interest ----------

def test_classify_interest_high():
    result = classify_interest("Customer interested, shared budget and timeline, asked to schedule site visit")
    assert result == "high"


def test_classify_interest_high_from_combined_signals():
    result = classify_interest("Customer interested and wants to follow-up next week")
    assert result == "high"


def test_classify_interest_medium_single_high_term():
    result = classify_interest("Customer seems interested")
    assert result == "medium"


def test_classify_interest_medium_from_medium_terms():
    result = classify_interest("Customer said maybe, would like to think about it")
    assert result == "medium"


def test_classify_interest_medium_send_details():
    result = classify_interest("Please send details about the project")
    assert result == "medium"


def test_classify_interest_none_for_dnc():
    result = classify_interest("Please do not call again, not interested")
    assert result == "none"


def test_classify_interest_none_wrong_number():
    result = classify_interest("This is a wrong number")
    assert result == "none"


def test_classify_interest_none_stop_call():
    result = classify_interest("Please stop calling me")
    assert result == "none"


def test_classify_interest_low_voicemail():
    result = classify_interest("Left a voicemail message")
    assert result == "low"


def test_classify_interest_low_no_answer():
    result = classify_interest("Call ended, no answer from customer")
    assert result == "low"


def test_classify_interest_low_minimal_text():
    result = classify_interest("Hi, ok, bye")
    assert result == "low"


def test_classify_interest_uses_ended_reason():
    result = classify_interest("Brief conversation", "voicemail")
    assert result == "low"


def test_classify_interest_negative_overrides_positive():
    """Negative signals should override positive ones."""
    result = classify_interest("Customer said interested but then said not interested, stop calling")
    assert result == "none"


# ---------- is_hot_lead ----------

def test_is_hot_lead_requires_high_and_context():
    assert is_hot_lead("high", "Interested in 2BHK in Bandra, budget 3 crore, this month") is True
    assert is_hot_lead("medium", "Interested in Bandra, budget 3 crore") is False


def test_is_hot_lead_locality_plus_budget():
    assert is_hot_lead("high", "Wants property in Powai, budget around 2 crore") is True


def test_is_hot_lead_budget_signals_only():
    assert is_hot_lead("high", "Looking for 3BHK with budget of 4 crore") is True


def test_is_hot_lead_not_enough_context():
    assert is_hot_lead("high", "Customer said yes, sounds good") is False


def test_is_hot_lead_rejects_non_high():
    assert is_hot_lead("low", "Interested in 2BHK in Bandra with 3 crore") is False
    assert is_hot_lead("none", "Budget 5 crore in Juhu") is False
