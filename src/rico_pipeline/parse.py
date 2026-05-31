"""View-hierarchy parsing (from lab Section 2)."""

from __future__ import annotations

import json


def parse_hierarchy(raw_json: str) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    try:
        tree = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    root = tree.get("activity", {}).get("root", tree) if isinstance(tree, dict) else None
    elements: list[tuple[str, str, tuple[int, int, int, int]]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        text = (node.get("text") or "").strip()
        cls = (node.get("class") or "").strip()
        if text or cls:
            element_type = cls.rsplit(".", 1)[-1] if cls else ""
            raw_bounds = node.get("bounds") or [0, 0, 0, 0]
            bounds = tuple(int(b) for b in raw_bounds) if len(raw_bounds) == 4 else (0, 0, 0, 0)
            elements.append((element_type, text, bounds))
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(reversed(children))
    return elements


def text_representation(elements: list[tuple[str, str, tuple[int, int, int, int]]]) -> str:
    with_text = [e for e in elements if e[1]]
    in_order = sorted(with_text, key=lambda e: (e[2][1], e[2][0]))
    return " ".join(text for _, text, _ in in_order)
