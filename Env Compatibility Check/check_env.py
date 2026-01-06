import sys
import subprocess
import requests
import manim

REQUIRED_PYTHON = (3, 9)
OLLAMA_URL = "http://localhost:11434/api/tags"
REQUIRED_MODEL = "gemma3:1b"

def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)

print("🔍 Running environment compatibility check...\n")

# Python version
if sys.version_info < REQUIRED_PYTHON:
    fail(f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required")

print(f"✅ Python {sys.version.split()[0]}")

# Manim
print(f"✅ Manim {manim.__version__}")

# FFmpeg
try:
    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ FFmpeg available")
except FileNotFoundError:
    fail("FFmpeg not found in PATH")

# Ollama server
try:
    r = requests.get(OLLAMA_URL, timeout=5)
    r.raise_for_status()
    models = [m["name"] for m in r.json().get("models", [])]
except Exception:
    fail("Ollama server not running (start with `ollama serve`)")

print("✅ Ollama server reachable")

# Required model
if REQUIRED_MODEL not in models:
    fail(f"Ollama model '{REQUIRED_MODEL}' not pulled")

print(f"✅ Ollama model '{REQUIRED_MODEL}' available")

print("\n🎉 Environment is fully compatible.")


"""
ollama --version
ollama pull gemma3:1b
ollama serve
python generate_script.py
python build_blueprint.py
python add_voiceover.py (y,y)
manim -pqh render_video.py Explainer
python add_voiceover.py (n,n)
ollama stop

"""
