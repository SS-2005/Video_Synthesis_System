from pathlib import Path
import json
import subprocess
from gtts import gTTS
import math
import re
import time

# Global variables at the top
SCRIPT_FILE = Path("script.json")
VIDEO_FILE = Path("media/videos/render_video/1080p60/Explainer.mp4")
AUDIO_DIR = Path("scene_audio")
FINAL_VIDEO = Path("final_with_voiceover.mp4")

def get_audio_duration(file_path):
    """Get duration of audio file using ffprobe"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return float(result.stdout.strip())
    return 0

def calculate_optimal_speed(narration_text, target_duration):
    """Calculate optimal reading speed for narration"""
    # Estimate words per minute (WPM) for different speeds
    # Normal: 150 WPM, Fast: 180 WPM, Very Fast: 200+ WPM
    
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
    
    # Remove excessive newlines and spaces
    clean_text = ' '.join(clean_text.split())
    
    # Calculate optimal speed
    if target_duration:
        speed_factor = calculate_optimal_speed(clean_text, target_duration)
        
        # For gTTS, we need to generate at normal speed then adjust
        # Generate audio
        try:
            tts = gTTS(text=clean_text, lang=lang, slow=False)
            tts.save(output_path)
            
            # Adjust speed using ffmpeg
            adjusted_path = output_path.parent / f"{output_path.stem}_adjusted{output_path.suffix}"
            
            cmd = [
                "ffmpeg", "-y",
                "-i", str(output_path),
                "-filter:a", f"atempo={speed_factor}",
                "-vn",
                str(adjusted_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Replace with adjusted audio
                output_path.unlink()
                adjusted_path.rename(output_path)
        except Exception as e:
            print(f"Error generating audio: {e}")
            # Fallback: generate without speed adjustment
            tts = gTTS(text=clean_text[:500], lang=lang, slow=False)
            tts.save(output_path)
    else:
        # Generate without speed adjustment
        try:
            tts = gTTS(text=clean_text[:5000], lang=lang, slow=False)
            tts.save(output_path)
        except:
            # If text is too long, split it
            chunks = [clean_text[i:i+4000] for i in range(0, len(clean_text), 4000)]
            temp_files = []
            
            for i, chunk in enumerate(chunks):
                temp_file = output_path.parent / f"temp_{i}.mp3"
                tts = gTTS(text=chunk, lang=lang, slow=False)
                tts.save(temp_file)
                temp_files.append(temp_file)
            
            # Concatenate chunks
            concat_list = output_path.parent / "concat.txt"
            with open(concat_list, "w") as f:
                for temp_file in temp_files:
                    f.write(f"file '{temp_file.resolve()}'\n")
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True)
            
            # Clean up
            for temp_file in temp_files:
                temp_file.unlink()
            concat_list.unlink()
    
    return get_audio_duration(output_path)

def analyze_script_for_timing(script):
    """Analyze script and suggest realistic durations"""
    print("\n📊 Script Analysis:")
    total_words = 0
    suggested_durations = []
    
    for i, scene in enumerate(script["scenes"], 1):
        narration = scene["narration"]
        words = len(re.findall(r'\b\w+\b', narration))
        total_words += words
        
        # Calculate realistic duration (150 words per minute = 2.5 words per second)
        suggested_seconds = words / 2.5
        
        # Minimum 8 seconds, maximum 30 seconds per scene
        suggested_seconds = max(8, min(suggested_seconds, 30))
        
        suggested_durations.append(suggested_seconds)
        
        print(f"Scene {i}: {words} words → {suggested_seconds:.1f}s suggested")
    
    print(f"\nTotal: {total_words} words → {sum(suggested_durations):.1f}s total ({sum(suggested_durations)/60:.1f}min)")
    print(f"Current durations sum to: {sum(s.get('length_seconds', 15) for s in script['scenes']):.1f}s")
    
    return suggested_durations

def main():
    # Use a local variable for the script file path
    script_file = SCRIPT_FILE
    
    if not script_file.exists():
        raise FileNotFoundError("script.json not found.")

    AUDIO_DIR.mkdir(exist_ok=True)

    with script_file.open("r", encoding="utf-8") as f:
        script = json.load(f)

    # Analyze script and suggest better durations
    suggested_durations = analyze_script_for_timing(script)
    
    # Ask user if they want to update durations
    update = input("\nUpdate scene durations based on analysis? (y/n): ").strip().lower()
    
    if update == 'y':
        for i, duration in enumerate(suggested_durations):
            script["scenes"][i]["length_seconds"] = round(duration, 1)
        
        # Save updated script
        with open("script_updated.json", "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2)
        print("✅ Updated script saved as script_updated.json")
        
        # Ask if we should use the updated script
        use_updated = input("Use updated script for rendering? (y/n): ").strip().lower()
        if use_updated == 'y':
            # Use the updated script file
            script_file = Path("script_updated.json")
            with script_file.open("r", encoding="utf-8") as f:
                script = json.load(f)

    audio_files = []
    actual_durations = []
    
    print("\n🔊 Generating optimized voiceover...")

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
        
        print(f"  Generated in {generation_time:.1f}s → {duration:.1f}s actual")

    # Calculate totals
    target_total = sum(scene.get("length_seconds", 15) for scene in script["scenes"])
    actual_total = sum(actual_durations)
    
    print(f"\n📊 Final Timing:")
    print(f"Target total: {target_total:.1f}s ({target_total/60:.1f}min)")
    print(f"Actual total: {actual_total:.1f}s ({actual_total/60:.1f}min)")
    print(f"Difference: {abs(target_total - actual_total):.1f}s")
    
    # Save timing report
    timing_report = {
        "scenes": [],
        "summary": {
            "target_total": target_total,
            "actual_total": actual_total,
            "difference": abs(target_total - actual_total)
        }
    }
    
    for i, (scene, target, actual) in enumerate(zip(script["scenes"], 
                                                     [s.get("length_seconds", 15) for s in script["scenes"]], 
                                                     actual_durations), 1):
        timing_report["scenes"].append({
            "scene": i,
            "title": scene["title"],
            "target_duration": target,
            "actual_duration": actual,
            "difference": abs(target - actual)
        })
    
    with open("timing_report.json", "w", encoding="utf-8") as f:
        json.dump(timing_report, f, indent=2)

    # Concatenate audio files
    print("\n🔗 Concatenating audio files...")
    concat_list = "audio_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for a in audio_files:
            f.write(f"file '{a.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        "voiceover.mp3"
    ], check=True)

    # Clean up
    Path(concat_list).unlink()

    # Check if video exists
    if not VIDEO_FILE.exists():
        print(f"\n⚠ Video file not found at {VIDEO_FILE}")
        print("Please run: manim -pqh render_video.py Explainer")
        return

    # Merge video with voiceover
    print("\n🎬 Merging video with voiceover...")
    
    # Get video duration
    video_duration = get_audio_duration(VIDEO_FILE)
    audio_duration = get_audio_duration("voiceover.mp3")
    
    print(f"Video duration: {video_duration:.1f}s ({video_duration/60:.1f}min)")
    print(f"Audio duration: {audio_duration:.1f}s ({audio_duration/60:.1f}min)")
    
    # Adjust audio to match video if needed
    if abs(video_duration - audio_duration) > 1.0:
        print(f"⚠ Adjusting audio to match video...")
        
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            Path("voiceover.mp3").unlink()
            Path(adjusted_audio).rename("voiceover.mp3")
            audio_duration = get_audio_duration("voiceover.mp3")
            print(f"✅ Adjusted to: {audio_duration:.1f}s")

    # Create final video
    subprocess.run([
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
    ], check=True)

    print(f"\n✅ Final video created: {FINAL_VIDEO.resolve()}")
    print(f"⏱️  Duration: {video_duration:.1f}s")
    print(f"🎵 Voiceover synced: {'Yes' if abs(video_duration - audio_duration) <= 1.0 else 'No'}")
    
    # Important instruction
    print("\n📝 IMPORTANT: If you used script_updated.json, update render_video.py to use it:")
    print("   Change SCRIPT_FILE = Path('script.json') to SCRIPT_FILE = Path('script_updated.json')")

if __name__ == "__main__":
    main()