"""Tests for the wiring between classification and presentation."""

import pytest

import app
import versions


def test_every_tone_has_a_css_class():
    """TONE_CLASS[tone] raises rather than defaulting, so it must be complete."""
    tones = {tone for _, tone, _ in versions.STATE_INFO.values()}
    assert tones <= set(app.TONE_CLASS)


@pytest.mark.parametrize("state", sorted(versions.STATE_INFO))
def test_offered_prompts_exist(state):
    """Every kind offered must have a label and a template on disk."""
    for upstream in (versions.UPSTREAM_OK, versions.UPSTREAM_NEWER):
        for kind in app.prompt_kinds(state, upstream, dif_passed=True):
            assert kind in app.PROMPT_LABELS
            assert (app.PROMPT_DIR / f"{kind}.md").is_file()


def test_in_proposed_never_offers_an_upload():
    """The upload already exists; offering to prepare another is wrong."""
    kinds = app.prompt_kinds(versions.IN_PROPOSED, versions.UPSTREAM_OK, True)
    assert kinds == ["investigate-proposed"]


def test_autosync_only_needs_a_human_after_dif():
    assert app.prompt_kinds(versions.AUTOSYNC_PENDING, versions.UPSTREAM_OK, False) == []
    assert app.prompt_kinds(versions.AUTOSYNC_PENDING, versions.UPSTREAM_OK, True) == ["sync"]


def test_load_packages_skips_comments_and_blanks(tmp_path):
    listing = tmp_path / "package-list.txt"
    listing.write_text("# header\n\nfoo\nbar # trailing\n")
    assert app.load_packages(listing) == ["foo", "bar"]
