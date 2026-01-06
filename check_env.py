import manim
import requests

print("Manim version:", manim.__version__)
print("Requests OK")
print("Ollama expected at http://localhost:11434")




"""
ollama --version
ollama pull gemma3:1b
ollama serve
python extract_style.py
python generate_script.py
python build_blueprint.py
python add_voiceover.py (y,y)
manim -pqh render_video.py Explainer
python add_voiceover.py (n,n)
ollama stop
"""