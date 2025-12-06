from game_automation.core.actions import VisualScript, VisualNode
from game_automation.core.automation import AutomationController


def duplicate_script_like_ui(base_script: VisualScript) -> VisualScript:
    import copy
    new_nodes = []
    node_id_mapping = {}
    for i, node in enumerate(base_script.nodes):
        new_id = f"node_{len(new_nodes)+1}"
        node_id_mapping[node.id] = new_id
        new_node = copy.deepcopy(node)
        new_node.id = new_id
        new_nodes.append(new_node)

    new_connections = {}
    for src_id, dst_id in base_script.connections.items():
        new_src = node_id_mapping.get(src_id, src_id)
        new_dst = node_id_mapping.get(dst_id, dst_id)
        new_connections[new_src] = new_dst

    for node in new_nodes:
        if node.type == "condition":
            if node.params.get("next_true"):
                old_id = node.params["next_true"]
                node.params["next_true"] = node_id_mapping.get(old_id, old_id)
            if node.params.get("next_false"):
                old_id = node.params["next_false"]
                node.params["next_false"] = node_id_mapping.get(old_id, old_id)
        elif node.type == "loop":
            if node.params.get("next_body"):
                old_id = node.params["next_body"]
                node.params["next_body"] = node_id_mapping.get(old_id, old_id)
            if node.params.get("next_after"):
                old_id = node.params["next_after"]
                node.params["next_after"] = node_id_mapping.get(old_id, old_id)

    return VisualScript(id="dup", name="dup", nodes=new_nodes, connections=new_connections)


def run_and_collect_ids(script: VisualScript, vision_result: dict) -> list[str]:
    ac = AutomationController(scale_factor=1.0)
    visited = []
    ac.on_node_executed = lambda nid, ok: visited.append(nid)
    ac.execute_visual_script(script, vision_result)
    return [nid for nid in visited if nid]


def test_duplicate_condition_next_params_rewritten_and_execution_path_matches():
    n1 = VisualNode(id="n1", type="condition", params={"mode": "label", "label": "A", "next_true": "n2", "next_false": "n3"})
    n2 = VisualNode(id="n2", type="sleep", params={"seconds": 0.0})
    n3 = VisualNode(id="n3", type="sleep", params={"seconds": 0.0})
    vs = VisualScript(id="s", name="s", nodes=[n1, n2, n3], connections={})

    vision_true = {"found_targets": [{"label": "A", "bbox": [0, 0, 10, 10]}]}
    orig_path = run_and_collect_ids(vs, vision_true)
    assert orig_path == ["n1", "n2"], f"unexpected original path: {orig_path}"

    dup = duplicate_script_like_ui(vs)
    dup_path = run_and_collect_ids(dup, vision_true)
    # Map back new ids to old based on order
    mapping_back = {f"node_{i+1}": nid for i, nid in enumerate(["n1", "n2", "n3"])}
    remapped = [mapping_back.get(nid, nid) for nid in dup_path]
    assert remapped == orig_path, f"duplicated path mismatch after remap: {dup_path} -> {remapped} vs {orig_path}"


def test_duplicate_loop_next_params_rewritten_and_execution_path_matches():
    l1 = VisualNode(id="l1", type="loop", params={"count": 2, "next_body": "n2", "next_after": "n3"})
    n2 = VisualNode(id="n2", type="sleep", params={"seconds": 0.0})
    n3 = VisualNode(id="n3", type="sleep", params={"seconds": 0.0})
    # Ensure loop body returns to loop node via connections for repeated iterations
    vs = VisualScript(id="s", name="s", nodes=[l1, n2, n3], connections={"n2": "l1"})

    vision = {"found_targets": []}
    orig_path = run_and_collect_ids(vs, vision)
    # Expected: loop body twice then after
    assert orig_path == ["l1", "n2", "l1", "n2", "l1", "n3"], f"unexpected original path: {orig_path}"

    dup = duplicate_script_like_ui(vs)
    dup_path = run_and_collect_ids(dup, vision)
    # New IDs will be node_1 (loop), node_2 (n2), node_3 (n3)
    mapping_back = {"node_1": "l1", "node_2": "n2", "node_3": "n3"}
    remapped = [mapping_back.get(nid, nid) for nid in dup_path]
    assert remapped == orig_path, f"duplicated loop path mismatch after remap: {dup_path} -> {remapped} vs {orig_path}"
