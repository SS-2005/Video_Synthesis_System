import json
import requests

# Ollama setup
MODEL = "gemma3:1b"
OLLAMA_URL = "http://localhost:11434/api/generate"

def ask(prompt):
    """Simple function to get response from Ollama"""
    payload = {
        "model": MODEL,
        "prompt": f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model",
        "stream": False,
        "options": {"num_predict": 200, "temperature": 0.3}
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            data = response.json()
            return data.get("response", "").strip()
        else:
            return f"Error: {response.status_code}"
    except:
        return "Error: Could not connect to Ollama"

# Get topic from user
topic = input("Enter topic for video: ").strip()
print(f"\nGenerating script for: {topic}")

# Generate content
intro = ask(f"Explain '{topic}' for in 2 to 3 sentences.")
how_it_works = ask(f"Explain how '{topic}' works in simple steps within 5 sentence")
applications = ask(f"Give 3 real-world applications of '{topic}' with in 3 sentence.")
conclusion = ask(f"Write a conclusion about why '{topic}' is important with in 2 to 3 sentence")

# Create script
script = {
    "topic": topic,
    "scenes": [
        {
            "title": "Introduction",
            "narration": intro,
            "bullets": ["Definition", "Purpose"],
            "length_seconds": 25
        },
        {
            "title": "How It Works",
            "narration": how_it_works,
            "bullets": ["Core idea", "Learning process"],
            "length_seconds": 35
        },
        {
            "title": "Applications",
            "narration": applications,
            "bullets": ["Real-world use", "Benefits"],
            "length_seconds": 30
        },
        {
            "title": "Conclusion",
            "narration": conclusion,
            "bullets": ["Summary", "Impact"],
            "length_seconds": 20
        }
    ]
}


# Save to file
with open("script.json", "w") as f:
    json.dump(script, f, indent=2)

print("\n✅ Done! Check script.json")