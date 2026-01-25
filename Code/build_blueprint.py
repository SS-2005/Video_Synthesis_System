import json

def main():
    style = json.load(open("style_profile.json", encoding="utf-8"))
    script = json.load(open("script.json", encoding="utf-8"))

    blueprint = {
        "style": style.get("style", "2D_explainer"),
        "scenes": []
    }

    for i, scene in enumerate(script["scenes"], 1):
        blueprint["scenes"].append({
            "scene_id": i,
            "title": scene["title"],
            "narration": scene["narration"],
            "visual_type": (
                "arrow_flow"
                if style.get("supporting_elements", {}).get("lines_and_arrows")
                else "text"
            ),
            "visual_instructions": scene["bullets"],
            "duration": scene["length_seconds"]
        })

    json.dump(blueprint, open("blueprint.json", "w", encoding="utf-8"), indent=2)
    print("✔ blueprint.json generated")

if __name__ == "__main__":
    main()