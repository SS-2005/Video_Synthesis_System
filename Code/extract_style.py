from PyPDF2 import PdfReader
from transformers import pipeline
import json
import re
import textwrap

# -----------------------
# Load PDF
# -----------------------
reader = PdfReader("analysis.pdf")
full_text = "\n".join(p.extract_text() or "" for p in reader.pages)

# -----------------------
# Chunk text to avoid token overflow
# -----------------------
def chunk_text(text, max_chars=1500):
    return textwrap.wrap(text, max_chars)

chunks = chunk_text(full_text)

# -----------------------
# Load model
# -----------------------
llm = pipeline(
    "text2text-generation",
    model="google/flan-t5-base",
    device=-1
)

# -----------------------
# Prompt template
# -----------------------
PROMPT_TEMPLATE = """
Extract a STRICT JSON style profile from the text below.

Required keys:
- style
- narrative_structure
- supporting_elements
- notes

Rules:
- Output ONLY valid JSON
- No explanations
- No markdown

Text:
{chunk}
"""

# -----------------------
# Aggregate responses
# -----------------------
json_candidates = []

for chunk in chunks:
    prompt = PROMPT_TEMPLATE.format(chunk=chunk)
    out = llm(prompt, max_new_tokens=256, do_sample=False)[0]["generated_text"]

    # Try to extract JSON safely
    match = re.search(r"\{[\s\S]*\}", out)
    if match:
        try:
            parsed = json.loads(match.group())
            json_candidates.append(parsed)
        except json.JSONDecodeError:
            pass

# -----------------------
# Merge or fallback
# -----------------------
if json_candidates:
    # Prefer the most complete one
    style_profile = max(json_candidates, key=lambda x: len(json.dumps(x)))
    style_profile["notes"] = style_profile.get("notes", "") + " | Extracted via chunked LLM parsing"
else:
    # HARD FALLBACK (guaranteed output)
    style_profile = {
        "style": "2D_explainer",
        "narrative_structure": {
            "introduction_minutes": 1,
            "significance_minutes": 1,
            "workflow_minutes": 3,
            "components_minutes": 1,
            "applications_minutes": 1,
            "conclusion_minutes": 1
        },
        "supporting_elements": {
            "lines_and_arrows": True,
            "flowcharts": "diagrammatic",
            "whiteboard_style": True,
            "animated_text": True,
            "ui_walkthrough": False,
            "characters": False,
            "infographics": "minimal"
        },
        "notes": "Fallback profile used due to LLM JSON extraction failure"
    }

# -----------------------
# Save output
# -----------------------
with open("style_profile.json", "w", encoding="utf-8") as f:
    json.dump(style_profile, f, indent=2)

print("✔ style_profile.json generated successfully")
