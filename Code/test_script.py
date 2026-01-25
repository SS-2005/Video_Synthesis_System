import sys
print(f"Python path: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    from gtts import gTTS
    print("✅ gTTS import successful")
except ImportError as e:
    print(f"❌ gTTS import failed: {e}")

try:
    import flask
    print("✅ Flask import successful")
except ImportError as e:
    print(f"❌ Flask import failed: {e}")

try:
    import manim
    print("✅ Manim import successful")
except ImportError as e:
    print(f"❌ Manim import failed: {e}")