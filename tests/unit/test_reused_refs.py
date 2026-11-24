"""Updates must not leave reuses of an old citation pointing at nothing."""

from nztcs_wiki_bot import apply
from nztcs_wiki_bot import speciesbox as sb

NEW_REF = '<ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>'
OLD_DEF = '<ref name="Hoare2017">{{cite journal |last=Hoare |year=2017 |title=Old}}</ref>'


def _article(status_ref: str, body: str) -> str:
    return (
        "{{Speciesbox\n| status = NV\n| status_system = NZTCS\n"
        f"| status_ref = {status_ref}\n| genus = Aenetus\n| species = virescens\n}}}}\n"
        f"{body}\n==References==\n{{{{Reflist}}}}\n"
    )


def _update(wt: str):
    return sb.patch_status(wt, "Aenetus", "virescens", "NT", "NZTCS2025", NEW_REF)


def test_reused_definition_moves_to_first_remaining_use():
    body = 'Described in 1843.<ref name="Hoare2017" /> Rare.<ref name="Hoare2017"/>'
    wt = _article(OLD_DEF, body)
    result = _update(wt)
    assert result.action == "update"
    assert f"| status_ref = {NEW_REF}" in result.after
    assert f"Described in 1843.{OLD_DEF} Rare.<ref name=\"Hoare2017\"/>" in result.after
    assert result.after.count(OLD_DEF) == 1


def test_bare_and_single_quoted_reuses_are_found():
    wt = _article(OLD_DEF, "Text.<ref name=Hoare2017 /> More.<ref name='Hoare2017' />")
    result = _update(wt)
    assert f"Text.{OLD_DEF} More." in result.after


def test_unreused_definition_is_simply_replaced():
    wt = _article(OLD_DEF, "No other citations.")
    result = _update(wt)
    assert "Hoare2017" not in result.after


def test_definition_kept_elsewhere_is_left_alone():
    # The old citation is also fully defined in the body: nothing to move.
    wt = _article('<ref name="Hoare2017" />', f"Text.{OLD_DEF}")
    result = _update(wt)
    assert result.after.count(OLD_DEF) == 1 and f"Text.{OLD_DEF}" in result.after


def test_moving_a_definition_is_idempotent():
    wt = _article(OLD_DEF, 'Text.<ref name="Hoare2017" />')
    first = _update(wt)
    second = sb.patch_status(first.after, "Aenetus", "virescens", "NT", "NZTCS2025", NEW_REF)
    assert second.action == "noop" and second.after == first.after


def test_names_are_case_sensitive():
    wt = _article(OLD_DEF, 'Text.<ref name="hoare2017" />')
    result = _update(wt)
    assert "Hoare2017" not in result.after  # a different name; not a reuse


def _entry(before: str, after: str) -> apply.Entry:
    return apply.Entry("1", "Aenetus virescens", "X", "NT", "update", before, after, "DIFF")


def test_apply_says_when_text_outside_the_infobox_changes():
    wt = _article(OLD_DEF, 'Text.<ref name="Hoare2017" />')
    result = _update(wt)
    assert apply.changes_outside_infobox(_entry(result.before, result.after))


def test_apply_is_quiet_when_only_the_infobox_changes():
    wt = _article(OLD_DEF, "No other citations.")
    result = _update(wt)
    assert not apply.changes_outside_infobox(_entry(result.before, result.after))
