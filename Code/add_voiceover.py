from pathlib import Path
import json
import subprocess
import math
import re
import time
import sys
import os

# Use ASCII-friendly indicators for Windows compatibility
CHECK = "[OK]"
ERROR = "[ERROR]"
INFO = "[INFO]"
WARNING = "[WARNING]"
ANALYSIS = "[ANALYSIS]"
AUDIO = "[AUDIO]"
CONCAT = "[CONCAT]"
MERGE = "[MERGE]"
TIME = "[TIME]"
SYNC = "[SYNC]"

# Try to import gTTS
try:
    from gtts import gTTS
    print(f"{CHECK} gTTS module imported successfully")
except ImportError as e:
    print(f"{ERROR} Error importing gTTS: {e}")
    print("Please install gtts with: pip install gtts")
    sys.exit(1)

# Global variables
SCRIPT_FILE = Path("script.json")
VIDEO_FILE = Path("media/videos/render_video/1080p60/Explainer.mp4")
AUDIO_DIR = Path("scene_audio")
FINAL_VIDEO = Path("final_with_voiceover.mp4")

def get_audio_duration(file_path):
    """Get duration of audio file using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return 0
    except Exception as e:
        print(f"{ERROR} Error getting audio duration: {e}")
        return 0

def calculate_optimal_speed(narration_text, target_duration):
    """Calculate optimal reading speed for narration"""
    # Count words
    words = len(re.findall(r'\b\w+\b', narration_text))
    
    # Calculate required WPM
    minutes = target_duration / 60
    required_wpm = words / minutes if minutes > 0 else 150
    
    # Determine speed adjustment
    if required_wpm <= 160:
        return 1.0  # Normal speed
    elif required_wpm <= 190:
        return 1.2  # Slightly faster
    elif required_wpm <= 220:
        return 1.4  # Faster
    else:
        return 1.6  # Very fast

def generate_scene_audio(text, output_path, target_duration=None, lang='en'):
    """Generate audio with optimized speed"""
    # Clean text for TTS
    clean_text = re.sub(r'[`*_#\-\[\]]', '', text)
    clean_text = ' '.join(clean_text.split())
    
    # Calculate optimal speed
    speed_factor = 1.0
    if target_duration:
        speed_factor = calculate_optimal_speed(clean_text, target_duration)
    
    try:
        # Generate audio with gTTS
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        tts.save(output_path)
        
        # Adjust speed if needed
        if speed_factor != 1.0:
            adjusted_path = output_path.parent / f"{output_path.stem}_adjusted{output_path.suffix}"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(output_path),
                "-filter:a", f"atempo={speed_factor}",
                "-vn",
                str(adjusted_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode == 0 and adjusted_path.exists():
                output_path.unlink(missing_ok=True)
                adjusted_path.rename(output_path)
        
        return get_audio_duration(output_path)
        
    except Exception as e:
        print(f"{ERROR} Error generating audio: {e}")
        # Fallback: try with shorter text
        try:
            clean_text = clean_text[:500]  # Limit text length
            tts = gTTS(text=clean_text, lang=lang, slow=False)
            tts.save(output_path)
            return get_audio_duration(output_path)
        except:
            return 0

def analyze_script_for_timing(script):
    """Analyze script and suggest realistic durations"""
    print(f"{ANALYSIS} Script Analysis:")
    total_words = 0
    suggested_durations = []
    
    for i, scene in enumerate(script["scenes"], 1):
        narration = scene["narration"]
        words = len(re.findall(r'\b\w+\b', narration))
        total_words += words
        
        # Calculate realistic duration (150 words per minute = 2.5 words per second)
        suggested_seconds = words / 2.5
        suggested_seconds = max(8, min(suggested_seconds, 30))
        suggested_durations.append(suggested_seconds)
        
        print(f"Scene {i}: {words} words -> {suggested_seconds:.1f}s suggested")
    
    print(f"\nTotal: {total_words} words -> {sum(suggested_durations):.1f}s total ({sum(suggested_durations)/60:.1f}min)")
    print(f"Current durations sum to: {sum(s.get('length_seconds', 15) for s in script['scenes']):.1f}s")
    
    return suggested_durations

def run_first_pass():
    """First run: generate voiceover and update timings"""
    if not SCRIPT_FILE.exists():
        print(f"{ERROR} script.json not found.")
        return False
    
    AUDIO_DIR.mkdir(exist_ok=True)
    
    with SCRIPT_FILE.open("r", encoding="utf-8") as f:
        script = json.load(f)
    
    # Analyze script and update durations
    suggested_durations = analyze_script_for_timing(script)
    
    for i, duration in enumerate(suggested_durations):
        script["scenes"][i]["length_seconds"] = round(duration, 1)
    
    # Save updated script
    with open("script_updated.json", "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)
    print(f"{CHECK} Updated script saved as script_updated.json")
    
    # Use the updated script
    script_file = Path("script_updated.json")
    with script_file.open("r", encoding="utf-8") as f:
        script = json.load(f)
    
    audio_files = []
    actual_durations = []
    
    print(f"\n{AUDIO} Generating optimized voiceover...")
    
    for i, scene in enumerate(script["scenes"], start=1):
        audio_path = AUDIO_DIR / f"scene_{i}.mp3"
        
        # Get target duration from script
        target_duration = scene.get("length_seconds", 15)
        
        print(f"\nGenerating Scene {i}: {target_duration}s target")
        
        # Generate audio with speed optimization
        start_time = time.time()
        duration = generate_scene_audio(
            scene["narration"], 
            audio_path, 
            target_duration=target_duration
        )
        generation_time = time.time() - start_time
        
        actual_durations.append(duration)
        audio_files.append(audio_path)
        
        print(f"  Generated in {generation_time:.1f}s -> {duration:.1f}s actual")
    
    # Calculate totals
    target_total = sum(scene.get("length_seconds", 15) for scene in script["scenes"])
    actual_total = sum(actual_durations)
    
    print(f"\n{TIME} Final Timing:")
    print(f"Target total: {target_total:.1f}s ({target_total/60:.1f}min)")
    print(f"Actual total: {actual_total:.1f}s ({actual_total/60:.1f}min)")
    print(f"Difference: {abs(target_total - actual_total):.1f}s")
    
    # Concatenate audio files
    print(f"\n{CONCAT} Concatenating audio files...")
    concat_list = "audio_concat.txt"
    try:
        with open(concat_list, "w", encoding="utf-8") as f:
            for a in audio_files:
                f.write(f"file '{a.resolve()}'\n")
        
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            "voiceover.mp3"
        ], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        print(f"{CHECK} Audio concatenated successfully")
        
    except Exception as e:
        print(f"{ERROR} Error concatenating audio: {e}")
        return False
    finally:
        if os.path.exists(concat_list):
            os.unlink(concat_list)
    
    print(f"\n{CHECK} First pass completed: Voiceover generated and script updated")
    return True

def run_second_pass():
    """Second run: merge voiceover with video"""
    if not VIDEO_FILE.exists():
        print(f"{WARNING} Video file not found at {VIDEO_FILE}")
        print("Please run Manim first: manim -pqh render_video.py Explainer")
        return False
    
    if not os.path.exists("voiceover.mp3"):
        print(f"{ERROR} voiceover.mp3 not found. Please run first pass.")
        return False
    
    print(f"{MERGE} Merging video with voiceover...")
    
    # Get video duration
    video_duration = get_audio_duration(VIDEO_FILE)
    audio_duration = get_audio_duration("voiceover.mp3")
    
    print(f"Video duration: {video_duration:.1f}s ({video_duration/60:.1f}min)")
    print(f"Audio duration: {audio_duration:.1f}s ({audio_duration/60:.1f}min)")
    
    # Adjust audio to match video if needed
    if abs(video_duration - audio_duration) > 1.0:
        print(f"{WARNING} Adjusting audio to match video...")
        
        # Calculate final speed adjustment
        speed_factor = audio_duration / video_duration
        
        # Apply speed adjustment
        adjusted_audio = "voiceover_adjusted.mp3"
        cmd = [
            "ffmpeg", "-y",
            "-i", "voiceover.mp3",
            "-filter:a", f"atempo={speed_factor}",
            "-vn",
            adjusted_audio
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0 and os.path.exists(adjusted_audio):
            if os.path.exists("voiceover.mp3"):
                os.unlink("voiceover.mp3")
            os.rename(adjusted_audio, "voiceover.mp3")
            audio_duration = get_audio_duration("voiceover.mp3")
            print(f"{CHECK} Adjusted to: {audio_duration:.1f}s")
    
    # Create final video
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(VIDEO_FILE),
            "-i", "voiceover.mp3",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(FINAL_VIDEO)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        print(f"\n{CHECK} Final video created: {FINAL_VIDEO.resolve()}")
        print(f"{TIME} Duration: {video_duration:.1f}s")
        
        if abs(video_duration - audio_duration) <= 1.0:
            print(f"{SYNC} Voiceover synced: Yes")
        else:
            print(f"{WARNING} Voiceover synced: No (difference: {abs(video_duration - audio_duration):.1f}s)")
        
        return True
        
    except Exception as e:
        print(f"{ERROR} Error creating final video: {e}")
        return False

def main():
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--first-run":
            success = run_first_pass()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--second-run":
            success = run_second_pass()
            sys.exit(0 if success else 1)
        else:
            print("Usage: python add_voiceover.py [--first-run | --second-run]")
            print("  --first-run: Generate voiceover and update timings")
            print("  --second-run: Merge voiceover with video")
            sys.exit(1)
    else:
        # Interactive mode (original behavior)
        run_first_pass()
        print("\n" + "="*50)
        print("Now run: manim -pqh render_video.py Explainer")
        print("Then run: python add_voiceover.py --second-run")
        print("="*50)

if __name__ == "__main__":
    main()