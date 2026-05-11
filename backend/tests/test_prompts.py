from core.prompts import PromptTemplates

def test_get_template_returns_string():
    tmpl = PromptTemplates.get_template("fair_npc")
    assert isinstance(tmpl, str)
    assert "峰位" in tmpl

def test_get_template_dsc():
    tmpl = PromptTemplates.get_template("dsc")
    assert "Tg" in tmpl

def test_get_template_unknown_falls_back_to_default():
    tmpl = PromptTemplates.get_template("unknown_type")
    assert isinstance(tmpl, str)
