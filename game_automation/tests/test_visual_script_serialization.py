from game_automation.core.actions import VisualScript, VisualNode
from PySide6.QtCore import QPointF


def test_visual_script_json_roundtrip():
    n1 = VisualNode(id="n1", type="click", params={"mode": "label", "label": "MATCH_BUTTON"}, position=QPointF(10, 20))
    n2 = VisualNode(id="n2", type="sleep", params={"seconds": 0.5}, position=QPointF(140, 20))
    vs = VisualScript(id="s1", name="demo", nodes=[n1, n2], connections={"n1": "n2"})
    text = vs.to_json(indent=2)
    vs2 = VisualScript.from_json(text)
    assert vs2.id == "s1"
    assert vs2.name == "demo"
    assert len(vs2.nodes) == 2
    assert vs2.nodes[0].id == "n1"
    assert vs2.connections["n1"] == "n2"
