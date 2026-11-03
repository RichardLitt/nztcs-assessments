from nztcs_wiki_bot import citation
from nztcs_wiki_bot.csv_loader import Row


def _row(**kw):
    base = {"reportName": "Lepidoptera 2025 (Hoare et al. 2026)", "reportYear": "2026"}
    base.update(kw)
    return Row.from_dict(base)


def test_ref_name_is_slug_safe():
    assert citation.ref_name("Lepidoptera 2025 (Hoare et al. 2026)") == "NZTCS-Lepidoptera-2025"
    name = citation.ref_name("Lepidoptera 2025 (Hoare et al. 2026)")
    assert " " not in name and "(" not in name


def test_build_ref_contents():
    name, ref = citation.build_ref(_row())
    assert name == "NZTCS-Lepidoptera-2025"
    assert "cite report" in ref
    assert "2026" in ref
    assert citation.TODO_AUTHORS in ref
    assert ref.startswith(f'<ref name="{name}">')
    assert ref.endswith("</ref>")


def test_build_ref_is_deterministic():
    a = citation.build_ref(_row())
    b = citation.build_ref(_row())
    assert a == b


def test_title_derivation():
    name, ref = citation.build_ref(_row())
    assert "Conservation status of New Zealand Lepidoptera, 2025" in ref
