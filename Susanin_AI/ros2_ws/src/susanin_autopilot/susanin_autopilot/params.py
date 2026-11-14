"""Объявление параметров ROS 2 по полям dataclass (имена вида ``группа.поле``)."""

from __future__ import annotations

from dataclasses import fields, replace


def declare_dataclass(node, prefix: str, defaults):
    """Объявить параметры узла по полям ``defaults`` и вернуть заполненный объект."""
    values = {}
    for item in fields(defaults):
        default = getattr(defaults, item.name)
        value = node.declare_parameter(f'{prefix}.{item.name}', default).value
        values[item.name] = list(value) if isinstance(default, list) else value
    return replace(defaults, **values)
