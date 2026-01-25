from flask import Flask, render_template, request, Response, send_file, jsonify
import json
import subprocess
import os
import sys
import time

app = Flask(__name__)

# Get the current Python executable path (should be from virtual environment)
PYTHON_PATH = sys.executable
print(f"Using Python from: {PYTHON_PATH}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate_script", methods=["POST"])
def generate_script():
    topic = request.json.get("topic")
    if not topic:
        return jsonify({"error": "No topic provided"}), 400
    
    try:
        # Run generate_script.py with the topic
        import requests
        
        MODEL = "gemma3:1b"
        OLLAMA_URL = "http://localhost:11434/api/generate"
        
        def ask(prompt):
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
        
        # Generate content
        print(f"Generating script for: {topic}")
        intro = ask(f"Explain '{topic}' in 2 to 3 sentences.")
        how_it_works = ask(f"Explain how '{topic}' works in simple steps within 5 sentences.")
        applications = ask(f"Give 3 real-world applications of '{topic}' within 3 sentences.")
        conclusion = ask(f"Write a conclusion about why '{topic}' is important within 2 to 3 sentences.")
        
        # Create script
        script_content = {
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
            json.dump(script_content, f, indent=2)
        
        return jsonify({
            "success": True,
            "script": script_content,
            "message": "Script generated successfully"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_script", methods=["POST"])
def update_script():
    updated_script = request.json.get("script")
    if not updated_script:
        return jsonify({"error": "No script provided"}), 400
    
    # Save updated script
    with open("script.json", "w") as f:
        json.dump(updated_script, f, indent=2)
    
    return jsonify({"success": True, "message": "Script updated successfully"})

def run_subprocess(command, timeout=600):
    """Run a subprocess and yield output in real-time"""
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            cwd=os.getcwd()
        )
        
        # Stream output in real-time
        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                # Clean and yield the line
                cleaned_line = line.strip()
                if cleaned_line:
                    yield cleaned_line
        
        # Wait for process to complete
        process.wait(timeout=timeout)
        return process.returncode
        
    except subprocess.TimeoutExpired:
        process.kill()
        yield "Process timed out"
        return 1
    except Exception as e:
        yield f"Error: {str(e)}"
        return 1

@app.route("/generate_video", methods=["GET"])
def generate_video():
    def event_stream():
        # Step 1: Build blueprint
        yield f"data: [STEP 1/4] Building blueprint...\n\n"
        try:
            # Import and run build_blueprint
            import build_blueprint
            build_blueprint.main()
            yield "data: [OK] Blueprint generated successfully\n\n"
        except Exception as e:
            yield f"data: [ERROR] Error building blueprint: {str(e)}\n\n"
            return
        
        # Step 2: Generate voiceover with timings
        yield f"data: [STEP 2/4] Generating voiceover and analyzing timings...\n\n"
        try:
            # Run add_voiceover.py --first-run
            for line in run_subprocess([PYTHON_PATH, 'add_voiceover.py', '--first-run'], timeout=300):
                yield f"data: {line}\n\n"
            
            # Check if voiceover was created
            if os.path.exists("voiceover.mp3"):
                yield "data: [OK] Voiceover generated successfully\n\n"
            else:
                yield "data: [ERROR] Voiceover file not created\n\n"
                return
                
        except Exception as e:
            yield f"data: [ERROR] Error generating voiceover: {str(e)}\n\n"
            return
        
        # Step 3: Render video with Manim
        yield f"data: [STEP 3/4] Rendering video with Manim (this may take a few minutes)...\n\n"
        try:
            # Check if script_updated.json exists
            if not os.path.exists("script_updated.json"):
                yield "data: [ERROR] script_updated.json not found\n\n"
                return
            
            # Check if video already exists
            video_path = "media/videos/render_video/1080p60/Explainer.mp4"
            if os.path.exists(video_path):
                yield "data: [INFO] Video already exists, skipping rendering\n\n"
            else:
                # Run manim command
                for line in run_subprocess([PYTHON_PATH, '-m', 'manim', '-pqh', 'render_video.py', 'Explainer'], timeout=600):
                    yield f"data: {line}\n\n"
            
            if os.path.exists("media/videos/render_video/1080p60/Explainer.mp4"):
                yield "data: [OK] Video rendered successfully\n\n"
            else:
                yield "data: [ERROR] Video file not found after rendering\n\n"
                return
                
        except Exception as e:
            yield f"data: [ERROR] Error rendering video: {str(e)}\n\n"
            return
        
        # Step 4: Merge final voiceover
        yield f"data: [STEP 4/4] Merging final voiceover with video...\n\n"
        try:
            # Run add_voiceover.py --second-run
            for line in run_subprocess([PYTHON_PATH, 'add_voiceover.py', '--second-run'], timeout=300):
                yield f"data: {line}\n\n"
            
            if os.path.exists("final_with_voiceover.mp4"):
                yield "data: [OK] Final video created successfully\n\n"
                yield "data: PIPELINE_COMPLETE\n\n"
            else:
                yield "data: [ERROR] Final video file not created\n\n"
                return
                
        except Exception as e:
            yield f"data: [ERROR] Error in final merging: {str(e)}\n\n"
            return
    
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/video")
def video():
    video_path = "final_with_voiceover.mp4"
    if os.path.exists(video_path):
        return send_file(
            video_path,
            mimetype="video/mp4",
            as_attachment=False,
            conditional=True
        )
    else:
        return jsonify({"error": "Video not found"}), 404

@app.route("/check_video")
def check_video():
    if os.path.exists("final_with_voiceover.mp4"):
        size = os.path.getsize("final_with_voiceover.mp4")
        return jsonify({"exists": True, "size": size, "path": os.path.abspath("final_with_voiceover.mp4")})
    else:
        return jsonify({"exists": False})

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, threaded=True)