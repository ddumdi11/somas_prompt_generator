"""JSON-Schema-Verträge für Faktencheck Plus (v0.13.0, PR 1).

Die Feldnamen sind **verbindlich** (Spec §3/S3): Refiner (S1) und Mapper (S2)
liefern in PR 2 Objekte gegen genau diese Schemas; PR 1 validiert Fixtures damit.
Bewusst abhängigkeitsfrei — ein kleiner Validator deckt die genutzte
JSON-Schema-Teilmenge ab (type/enum/required/properties/items/minimum/maximum),
statt eine externe `jsonschema`-Dependency einzuführen.
"""
from __future__ import annotations

# --- Erlaubte Wertemengen (auch von models.py genutzt) --------------------

# Claim-Typen: die 6 faktischen (S1) + opinion/interpretation, damit Gate 1
# (exclude_claim_types) überhaupt greifen kann, falls ein Nicht-Faktum aus
# Stufe 1 durchrutscht.
CLAIM_TYPES = (
    "quantitative", "causal", "hard_fact", "prognosis",
    "source_attribution", "methodological", "opinion", "interpretation",
)
ARGUMENT_ROLES = (
    "core_claim", "supporting_premise", "context", "example", "metadata",
)
COUNTERFACTUAL_IMPACT = ("high", "medium", "low")

IMPORTANCE_DIMS = (
    "thesis_proximity", "conclusion_dependency", "harm_potential",
    "reach_mobilization", "concreteness",
)
RESEARCH_VALUE_DIMS = (
    "non_triviality", "recency", "contestedness",
    "source_access", "evidence_gap", "discrepancy_potential",
)
RATING_DIMS = IMPORTANCE_DIMS + RESEARCH_VALUE_DIMS


# --- Schemas (JSON-Schema-Teilmenge) --------------------------------------

REFINED_CLAIM_SCHEMA: dict = {
    "type": "object",
    "required": [
        "claim_id", "original_text", "normalized_claim", "claim_type", "entities",
    ],
    "properties": {
        "claim_id": {"type": "string"},
        "parent_id": {"type": ["string", "null"]},
        "original_text": {"type": "string"},
        "normalized_claim": {"type": "string"},
        "claim_type": {"enum": list(CLAIM_TYPES)},
        "entities": {"type": "array", "items": {"type": "string"}},
        "timeframe": {"type": ["string", "null"]},
        "metric": {"type": ["string", "null"]},
    },
}

ARGUMENT_MAPPING_SCHEMA: dict = {
    "type": "object",
    "required": ["claim_id", "argument_role", "counterfactual_impact", "ratings"],
    "properties": {
        "claim_id": {"type": "string"},
        "argument_role": {"enum": list(ARGUMENT_ROLES)},
        "counterfactual_impact": {"enum": list(COUNTERFACTUAL_IMPACT)},
        "ratings": {
            "type": "object",
            "required": list(RATING_DIMS),
            "properties": {
                dim: {"type": "integer", "minimum": 0, "maximum": 5}
                for dim in RATING_DIMS
            },
        },
        "reason": {"type": "string"},
    },
}


class SchemaError(ValueError):
    """Ein Instanzobjekt verletzt seinen JSON-Schema-Vertrag."""


_PY_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _matches_type(value: object, type_name: str) -> bool:
    """Prüft einen einzelnen JSON-Schema-Typ (bool ist NICHT integer/number)."""
    if type_name in ("integer", "number"):
        if isinstance(value, bool):
            return False
        return isinstance(value, int) if type_name == "integer" else isinstance(value, (int, float))
    if type_name == "boolean":
        return isinstance(value, bool)
    return isinstance(value, _PY_TYPES[type_name])


def validate(instance: object, schema: dict, path: str = "$") -> None:
    """Validiert ``instance`` gegen ``schema`` (unterstützte JSON-Schema-Teilmenge).

    Args:
        instance: Das zu prüfende Objekt.
        schema: Schema-Dict (type/enum/required/properties/items/minimum/maximum).
        path: Pfad zum aktuellen Knoten (für sprechende Fehlermeldungen).

    Raises:
        SchemaError: Bei der ersten festgestellten Verletzung.
    """
    if "enum" in schema:
        if instance not in schema["enum"]:
            raise SchemaError(f"{path}: {instance!r} nicht in {schema['enum']}")

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_matches_type(instance, t) for t in types):
            raise SchemaError(f"{path}: Typ {type(instance).__name__} passt nicht zu {types}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaError(f"{path}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                raise SchemaError(f"{path}: Pflichtfeld '{req}' fehlt")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                validate(instance[key], subschema, f"{path}.{key}")

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            validate(item, schema["items"], f"{path}[{i}]")
