from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

STYLE_PATH = Path("style_profile.json")
SCRIPT_PATH = Path("script.json")
BLUEPRINT_PATH = Path("blueprint.json")


def load_json(path: Path, fallback: Dict | None = None) -> Dict:
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


style = load_json(STYLE_PATH, {
    "style": "2D_explainer",
    "color_palette": ["#2563eb", "#0f172a", "#f8fafc"],
    "supporting_elements": {"lines_and_arrows": True},
})
script = load_json(SCRIPT_PATH)
if not script:
    raise FileNotFoundError("script.json not found. Run generate_script.py first.")


def choose_visual_type(scene: Dict, style: Dict) -> str:
    title = (scene.get("title") or "").lower()
    if "introduction" in title:
        return "concept_intro"
    if "how it works" in title:
        return "process_flow"
    if "applications" in title:
        return "use_case_grid"
    if "conclusion" in title:
        return "impact_summary"
    if style.get("supporting_elements", {}).get("lines_and_arrows"):
        return "arrow_flow"
    return "text"


scenes: List[Dict] = []
for i, scene in enumerate(script.get("scenes", []), start=1):
    scenes.append(
        {
            "scene_id": i,
            "title": scene.get("title", f"Scene {i}"),
            "narration": scene.get("narration", ""),
            "visual_type": choose_visual_type(scene, style),
            "visual_instructions": scene.get("bullets", []),
            "duration": scene.get("length_seconds", 20),
            "citations": scene.get("citations", []),
            "compliance_notes": scene.get("compliance_notes", []),
            "localization_notes": scene.get("localization_notes", []),
        }
    )

blueprint = {
    "topic": script.get("topic", "Untitled Topic"),
    "audience": script.get("audience", "intermediate"),
    "language": script.get("language", "English"),
    "goal": script.get("goal", "explainer"),
    "style": style.get("style", "2D_explainer"),
    "retrieval_used": script.get("retrieval_used", False),
    "source_summary": script.get("source_summary", []),
    "policy_flags": script.get("policy_flags", []),
    "scenes": scenes,
}

BLUEPRINT_PATH.write_text(json.dumps(blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
print("✔ blueprint.json generated")
