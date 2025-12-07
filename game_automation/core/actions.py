from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any, Optional
from PySide6.QtCore import QPointF
import json


ActionType = Literal["click", "key", "sleep", "find_color", "condition", "loop", "find_image"]


@dataclass
class Action:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionSequence:
    name: str = "Unnamed Sequence"
    actions: List[Action] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "actions": [asdict(a) for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionSequence":
        name = data.get("name", "Imported Sequence")
        actions_data = data.get("actions", [])
        actions: List[Action] = []
        for a in actions_data:
            actions.append(Action(
                type=a.get("type", "click"),
                params=a.get("params", {}),
            ))
        return cls(name=name, actions=actions)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "ActionSequence":
        data = json.loads(text)
        return cls.from_dict(data)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Action Sequence: {self.name}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Name: `{self.name}`")
        lines.append(f"- Actions: **{len(self.actions)}**")
        lines.append("")
        lines.append("## Actions")
        lines.append("")
        lines.append("| # | Type | Params |")
        lines.append("|---|------|--------|")
        for idx, a in enumerate(self.actions, start=1):
            params_json = json.dumps(a.params, ensure_ascii=False)
            params_md = params_json.replace("|", "\\|")
            lines.append(f"| {idx} | `{a.type}` | `{params_md}` |")
        lines.append("")
        lines.append("## Raw JSON")
        lines.append("")
        lines.append("```json")
        lines.append(self.to_json(indent=2))
        lines.append("```")
        lines.append("")
        return "\n".join(lines)


# ----- Visual Script model -----

@dataclass
class VisualNode:
    id: str
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    position: QPointF = field(default_factory=lambda: QPointF(0.0, 0.0))
    outputs: List[str] = field(default_factory=list)
    comment: Optional[str] = None  # Optional comment text for the node

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "position": [self.position.x(), self.position.y()],
            "outputs": list(self.outputs),
        }
        # Only include comment if it's not None
        if self.comment is not None:
            result["comment"] = self.comment
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualNode":
        pos = data.get("position", [0.0, 0.0])
        qpos = QPointF(float(pos[0]), float(pos[1]))
        return cls(
            id=str(data.get("id", "")),
            type=data.get("type", "click"),  # type: ignore
            params=data.get("params", {}),
            position=qpos,
            outputs=list(data.get("outputs", [])),
            comment=data.get("comment"),  # Backward compatible: defaults to None if missing
        )


@dataclass
class VisualScript:
    id: str = ""
    name: str = "Unnamed Visual Script"
    nodes: List[VisualNode] = field(default_factory=list)
    connections: Dict[str, str] = field(default_factory=dict)
    groups: Dict[str, List[str]] = field(default_factory=dict)  # Group name -> list of node IDs

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": dict(self.connections),
        }
        # Only include groups if it's not empty
        if self.groups:
            result["groups"] = dict(self.groups)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualScript":
        nodes_data = data.get("nodes", [])
        nodes: List[VisualNode] = [VisualNode.from_dict(nd) for nd in nodes_data]
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", "Unnamed Visual Script"),
            nodes=nodes,
            connections=dict(data.get("connections", {})),
            groups=dict(data.get("groups", {})),  # Backward compatible: defaults to empty dict if missing
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "VisualScript":
        data = json.loads(text)
        return cls.from_dict(data)

