from duckmind.cli import THEME, _model_choices, _parse_choice, _print_models
from duckmind.ui import UI


def test_model_choices_keep_catalog_order_and_access():
    choices = _model_choices()
    assert choices[0]["id"] == "gpt-6-luna"
    assert choices[0]["alias"] == "luna"
    assert choices[0]["access"] == "free"
    assert any(choice["access"] == "Pro subscription" for choice in choices)


def test_model_picker_accepts_number_alias_and_id():
    choices = _model_choices()
    assert _parse_choice("1", choices) == ("gpt-6-luna", True)
    assert _parse_choice("luna", choices) == ("gpt-6-luna", True)
    assert _parse_choice("claude-haiku-4-5", choices) == ("claude-haiku-4-5", True)


def test_free_model_filter_excludes_subscription_tiers():
    free = _model_choices("free")
    assert free
    assert all(choice["access"] == "free" for choice in free)
    assert "gpt-5.6-sol" not in {choice["id"] for choice in free}


def test_models_table_marks_the_current_model(capsys):
    _print_models(UI(THEME, enabled=False), "gpt-6-luna")
    output = capsys.readouterr().out
    assert "Models · DuckMind" in output
    assert "Current: gpt-6-luna" in output
    assert "gpt-5.6-sol" in output


def test_free_models_table_excludes_subscription_models(capsys):
    _print_models(UI(THEME, enabled=False), "gpt-6-luna", "free")
    output = capsys.readouterr().out
    assert "Models · DuckMind · free" in output
    assert "gpt-5.6-sol" not in output
    assert "gpt-5.6-terra" not in output
