from core.actions import Action, ActionSequence


def test_actions_json_roundtrip():
    seq = ActionSequence(name="demo", actions=[
        Action(type="click", params={"mode": "label", "label": "MATCH_BUTTON"}),
        Action(type="sleep", params={"seconds": 0.5}),
        Action(type="key", params={"key": "space", "duration": 0.1}),
    ])
    text = seq.to_json(indent=2)
    seq2 = ActionSequence.from_json(text)
    assert seq2.name == "demo"
    assert len(seq2.actions) == 3
    assert seq2.actions[0].type == "click"
    assert seq2.actions[1].params["seconds"] == 0.5


def test_to_markdown_contains_sections():
    seq = ActionSequence(name="md_demo", actions=[
        Action(type="sleep", params={"seconds": 1.0})
    ])
    md = seq.to_markdown()
    assert "# Action Sequence: md_demo" in md
    assert "## Raw JSON" in md

