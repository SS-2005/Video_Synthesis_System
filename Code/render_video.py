from manim import *
import json
import os

class Explainer(Scene):
    def construct(self):
        # Try to use script_updated.json first, then fall back to script.json
        script_file = "script_updated.json"
        if not os.path.exists(script_file):
            script_file = "script.json"
            if not os.path.exists(script_file):
                raise FileNotFoundError("script.json not found. Run generate_script.py first.")

        with open(script_file, "r", encoding="utf-8") as f:
            script = json.load(f)

        total_scenes = len(script["scenes"])
        
        for scene_idx, scene in enumerate(script["scenes"], 1):
            self.clear()

            # ---------- TITLE ----------
            title = Text(scene["title"], font_size=48, color=WHITE)
            title.to_edge(UP, buff=0.5)
            
            # Progress indicator
            progress_text = Text(f"Scene {scene_idx}/{total_scenes}", font_size=20, color=GRAY)
            progress_text.to_corner(DR, buff=0.3)
            
            self.play(
                Write(title),
                FadeIn(progress_text)
            )
            self.wait(0.5)

            # ---------- NARRATION TEXT ----------
            narration_text = scene["narration"]
            
            # Clean up markdown formatting for display
            import re
            narration_text = re.sub(r'\*\*(.*?)\*\*', r'\1', narration_text)
            narration_text = re.sub(r'\*(.*?)\*', r'\1', narration_text)
            narration_text = re.sub(r'`(.*?)`', r'\1', narration_text)
            
            # Split into chunks that fit the screen
            max_chars_per_line = 65
            max_lines = 8
            
            lines = []
            for paragraph in narration_text.split('\n'):
                if paragraph.strip() == '':
                    continue
                    
                words = paragraph.split()
                current_line = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) + 1 <= max_chars_per_line:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = len(word)
                
                if current_line:
                    lines.append(' '.join(current_line))
            
            # Take only first max_lines
            display_lines = lines[:max_lines]
            
            narration_paragraph = Paragraph(
                *display_lines,
                alignment="left",
                font_size=26,
                line_spacing=0.5,
                color=WHITE
            )
            
            # Scale if too tall
            if narration_paragraph.height > config.frame_height * 0.5:
                narration_paragraph.scale_to_fit_height(config.frame_height * 0.5)
            
            # Create rectangle
            narration_box = Rectangle(
                width=narration_paragraph.width + 0.8,
                height=narration_paragraph.height + 0.4,
                color=BLUE,
                stroke_width=2,
                fill_color=BLACK,
                fill_opacity=0.7
            )
            
            narration_group = VGroup(narration_box, narration_paragraph)
            narration_group.next_to(title, DOWN, buff=0.6)
            
            self.play(FadeIn(narration_group), run_time=1.5)
            
            # Add visual element
            visual_element = self.create_visual_element(scene_idx, scene["title"])
            if visual_element:
                visual_element.scale(0.6)
                visual_element.next_to(narration_group, DOWN, buff=0.4)
                self.play(DrawBorderThenFill(visual_element), run_time=1.5)
            
            # Wait based on scene duration
            scene_duration = scene.get("length_seconds", 15)
            animation_time = 1 + 0.5 + 1.5 + (1.5 if visual_element else 0)
            remaining_time = scene_duration - animation_time
            
            if remaining_time > 0:
                self.wait(remaining_time)
            
            # Clear for next scene
            fade_outs = [
                FadeOut(title),
                FadeOut(progress_text),
                FadeOut(narration_group)
            ]
            
            if visual_element:
                fade_outs.append(FadeOut(visual_element))
            
            self.play(*fade_outs, run_time=1)
            self.wait(0.5)
    
    def create_visual_element(self, scene_idx, title):
        """Create simple visual elements based on scene content"""
        title_lower = title.lower()
        
        if "intro" in title_lower:
            # AI brain visualization
            brain = Circle(radius=0.6, color=GREEN, stroke_width=3)
            neurons = VGroup(*[
                Dot(point=brain.point_from_proportion(i/6), color=YELLOW, radius=0.05)
                for i in range(6)
            ])
            connections = VGroup(*[
                Line(neurons[i].get_center(), neurons[(i+1)%6].get_center(), 
                     color=BLUE, stroke_width=1)
                for i in range(6)
            ])
            return VGroup(brain, neurons, connections)
        
        elif "how" in title_lower and "work" in title_lower:
            # Process flow
            step1 = Circle(radius=0.3, color=BLUE, stroke_width=2)
            step2 = Circle(radius=0.3, color=GREEN, stroke_width=2)
            step3 = Circle(radius=0.3, color=RED, stroke_width=2)
            
            step1.move_to(LEFT * 1.5)
            step2.move_to(ORIGIN)
            step3.move_to(RIGHT * 1.5)
            
            arrow1 = Arrow(step1.get_right(), step2.get_left(), buff=0.1)
            arrow2 = Arrow(step2.get_right(), step3.get_left(), buff=0.1)
            
            return VGroup(step1, step2, step3, arrow1, arrow2)
        
        elif "applicat" in title_lower:
            # Application icons
            netflix = Rectangle(width=0.7, height=0.5, color=RED, stroke_width=2)
            bank = Rectangle(width=0.7, height=0.5, color=GREEN, stroke_width=2)
            medical = Rectangle(width=0.7, height=0.5, color=BLUE, stroke_width=2)
            
            netflix.move_to(LEFT * 1.5)
            bank.move_to(ORIGIN)
            medical.move_to(RIGHT * 1.5)
            
            netflix_text = Text("TV", font_size=16, color=WHITE).move_to(netflix)
            bank_text = Text("$", font_size=20, color=WHITE).move_to(bank)
            medical_text = Text("+", font_size=20, color=WHITE).move_to(medical)
            
            return VGroup(netflix, bank, medical, netflix_text, bank_text, medical_text)
        
        elif "conclus" in title_lower:
            # Impact visualization
            center = Dot(color=YELLOW, radius=0.08)
            waves = VGroup(*[
                Circle(radius=i*0.4, color=WHITE, stroke_width=2, stroke_opacity=0.8-i*0.2)
                for i in range(1, 3)
            ])
            waves.move_to(ORIGIN)
            return VGroup(center, waves)
        
        return None

if __name__ == "__main__":
    config.media_width = "100%"
    config.frame_rate = 30
    config.pixel_width = 1920
    config.pixel_height = 1080
    config.background_color = "#1a1a1a"