from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Component:
    ref: str
    kind: str
    value: str
    nodes: tuple[str, ...]
    model: str | None = None


@dataclass(slots=True)
class Analysis:
    command: str


@dataclass(slots=True)
class CircuitSpec:
    name: str
    components: list[Component] = field(default_factory=list)
    analyses: list[Analysis] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    def add(self, ref: str, kind: str, value: str, *nodes: str, model: str | None = None) -> "CircuitSpec":
        self.components.append(Component(ref=ref, kind=kind, value=value, nodes=tuple(nodes), model=model))
        return self

    def analyze(self, command: str) -> "CircuitSpec":
        self.analyses.append(Analysis(command=command))
        return self

    def add_model(self, model_line: str) -> "CircuitSpec":
        self.models.append(model_line)
        return self
