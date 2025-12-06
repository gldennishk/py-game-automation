from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any
import json


ActionType = Literal["click", "key", "sleep"]


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

