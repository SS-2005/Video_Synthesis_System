from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests

from rag_utils import SimpleRAG, ensure_default_kb_readme

MODEL = "gemma3:1b"
OLLAMA_URL = "http://localhost:11434/api/generate"
SCRIPT_PATH = Path("script.json")
STYLE_PATH = Path("style_profile.json")
TOP_K_RETRIEVALS = 4


def ask_model(prompt: str, temperature: float = 0.25, num_predict: int = 700) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
        },
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=240)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
    except Exception as exc:
        return f"ERROR_CALLING_OLLAMA: {exc}"


def ask_json(prompt: str) -> Dict:
    raw = ask_model(prompt, temperature=0.15, num_predict=1200)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return valid JSON. Raw output:\n{raw[:1000]}")
    text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse model JSON: {exc}\nRaw output:\n{text[:1200]}") from exc


def load_style_profile() -> Dict:
    if STYLE_PATH.exists():
        try:
            return json.loads(STYLE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "style": "2D_explainer",
        "tone": "clear, professional, explanatory",
        "audience_default": "intermediate",
        "supporting_elements": {"lines_and_arrows": True},
    }


def collect_inputs() -> Dict[str, str]:
    print("\n=== Enhanced Video Synthesis Script Generator ===")
    topic = input("Enter topic for video: ").strip()
    audience = input("Audience level [beginner/intermediate/advanced] (default: intermediate): ").strip() or "intermediate"
    language = input("Output language (default: English): ").strip() or "English"
    goal = input("Video goal/use-case (default: explainer): ").strip() or "explainer"
    retrieval_hint = input("Optional retrieval hint (example: product policy / chapter 3 / brand guide): ").strip()
    return {
        "topic": topic,
        "audience": audience,
        "language": language,
        "goal": goal,
        "retrieval_hint": retrieval_hint,
    }


def build_retrieval_context(topic: str, retrieval_hint: str = "") -> Dict:
    ensure_default_kb_readme()
    rag = SimpleRAG()
    indexed = rag.build_index()
    query = topic if not retrieval_hint else f"{topic} {retrieval_hint}".strip()
    chunks = rag.retrieve(query, top_k=TOP_K_RETRIEVALS) if indexed else []
    context = rag.format_context(chunks)
    return {
        "indexed_chunks": indexed,
        "query": query,
        "chunks": [chunk.to_dict() for chunk in chunks],
        "context_text": context,
    }


def build_prompt(inputs: Dict[str, str], retrieval: Dict, style: Dict) -> str:
    context_text = retrieval.get("context_text") or "NO_RETRIEVAL_CONTEXT"
    tone = style.get("tone", "clear, professional, explanatory")
    visual_style = style.get("style", "2D_explainer")

    return f"""
You are generating a structured explainer-video script for an automated video pipeline.

Requirements:
- Topic: {inputs['topic']}
- Audience level: {inputs['audience']}
- Language: {inputs['language']}
- Goal: {inputs['goal']}
- Tone: {tone}
- Visual style: {visual_style}

Use the retrieved knowledge below if it is relevant and factual. Do not invent citations. If retrieval is missing, still answer carefully.

RETRIEVED_CONTEXT:
{context_text}

Return STRICT JSON only with this schema:
{{
  "topic": "string",
  "retrieval_used": true,
  "source_summary": ["short source note 1", "short source note 2"],
  "scenes": [
    {{
      "title": "Introduction",
      "narration": "4 to 6 clear sentences",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "length_seconds": 20,
      "citations": ["filename or source note"],
      "compliance_notes": ["claim grounded in source", "no medical/legal advice"],
      "localization_notes": ["language adaptation note"]
    }}
  ]
}}

Scene plan must have exactly 4 scenes in this order:
1. Introduction
2. How It Works
3. Applications
4. Conclusion

Hard constraints:
- Keep the explanation concise enough for a 90-130 second total video.
- Narration must be explanation-first, not marketing fluff.
- Bullets must be render-friendly and short.
- If retrieved context contains concrete facts, reflect them in narration.
- If a statement is uncertain, phrase it cautiously.
- Avoid markdown.
- Output JSON only.
""".strip()


def sanitize_script(data: Dict, retrieval: Dict, inputs: Dict[str, str]) -> Dict:
    required_titles = ["Introduction", "How It Works", "Applications", "Conclusion"]
    scenes: List[Dict] = data.get("scenes") or []
    if len(scenes) != 4:
        raise ValueError(f"Expected 4 scenes, got {len(scenes)}")

    clean_scenes: List[Dict] = []
    default_durations = [24, 34, 30, 18]

    for idx, scene in enumerate(scenes):
        title = scene.get("title") or required_titles[idx]
        narration = str(scene.get("narration") or "").strip()
        bullets = scene.get("bullets") or []
        bullets = [str(b).strip() for b in bullets if str(b).strip()][:4]
        if not bullets:
            bullets = ["Key idea", "Core point"]
        citations = [str(c).strip() for c in (scene.get("citations") or []) if str(c).strip()]
        compliance_notes = [str(c).strip() for c in (scene.get("compliance_notes") or []) if str(c).strip()]
        localization_notes = [str(c).strip() for c in (scene.get("localization_notes") or []) if str(c).strip()]
        duration = scene.get("length_seconds", default_durations[idx])
        try:
            duration = int(round(float(duration)))
        except Exception:
            duration = default_durations[idx]
        duration = max(12, min(duration, 40))
        clean_scenes.append(
            {
                "title": required_titles[idx],
                "narration": narration,
                "bullets": bullets,
                "length_seconds": duration,
                "citations": citations,
                "compliance_notes": compliance_notes,
                "localization_notes": localization_notes,
            }
        )

    policy_flags = run_policy_scan(clean_scenes)

    return {
        "topic": data.get("topic") or inputs["topic"],
        "audience": inputs["audience"],
        "language": inputs["language"],
        "goal": inputs["goal"],
        "retrieval_used": bool(retrieval.get("chunks")),
        "retrieval_query": retrieval.get("query", inputs["topic"]),
        "source_summary": data.get("source_summary") or summarize_sources(retrieval),
        "sources": retrieval.get("chunks") or [],
        "policy_flags": policy_flags,
        "scenes": clean_scenes,
    }


def summarize_sources(retrieval: Dict) -> List[str]:
    items = []
    for chunk in retrieval.get("chunks", []):
        filename = chunk.get("metadata", {}).get("filename") or chunk.get("source")
        score = chunk.get("score")
        items.append(f"{filename} (score={score})")
    return items[:4]


def run_policy_scan(scenes: List[Dict]) -> List[str]:
    banned_patterns = {
        r"\bguaranteed\b": "Avoid absolute guarantee language.",
        r"\b100%\b": "Avoid unverifiable certainty claims.",
        r"\bperfect\b": "Avoid exaggerated quality claims.",
        r"\bcure\b": "Avoid medical overclaim language.",
        r"\blegal advice\b": "Avoid direct legal advice phrasing.",
    }
    flags: List[str] = []
    full_text = "\n".join(scene.get("narration", "") for scene in scenes)
    for pattern, message in banned_patterns.items():
        if re.search(pattern, full_text, flags=re.IGNORECASE):
            flags.append(message)
    return flags


def maybe_revise_for_policy(script: Dict) -> Dict:
    if not script.get("policy_flags"):
        return script
    revision_prompt = f"""
You are revising a JSON script to remove policy/compliance issues.
Problems found: {json.dumps(script['policy_flags'])}

Return the SAME JSON schema, preserving scene order, topic, and structure.
Tone must stay professional and factual.
Current script:
{json.dumps(script, ensure_ascii=False, indent=2)}
""".strip()
    revised = ask_json(revision_prompt)
    revised["policy_flags"] = []
    return revised


def save_script(script: Dict) -> None:
    SCRIPT_PATH.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    inputs = collect_inputs()
    style = load_style_profile()
    retrieval = build_retrieval_context(inputs["topic"], inputs["retrieval_hint"])

    if retrieval["indexed_chunks"]:
        print(f"\nIndexed chunks: {retrieval['indexed_chunks']}")
        print(f"Retrieved grounding chunks: {len(retrieval['chunks'])}")
    else:
        print("\nNo knowledge-base files found. Continuing without retrieval grounding.")

    prompt = build_prompt(inputs, retrieval, style)
    initial = ask_json(prompt)
    script = sanitize_script(initial, retrieval, inputs)
    script = maybe_revise_for_policy(script)
    script = sanitize_script(script, retrieval, inputs)
    save_script(script)

    print("\n✅ script.json generated")
    print(f"Topic: {script['topic']}")
    print(f"Retrieval used: {script['retrieval_used']}")
    print(f"Policy flags: {len(script['policy_flags'])}")
    print("Scene titles:", ", ".join(scene["title"] for scene in script["scenes"]))


if __name__ == "__main__":
    main()
