"""Generate test audio files using Windows built-in TTS (offline)."""
import pyttsx3
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

engine = pyttsx3.init()

# List available voices
voices = engine.getProperty("voices")
print("Available voices:")
for v in voices:
    print(f"  - {v.id} | {v.name} | {v.languages}")

# English test text (~40s of speech, tests chunking)
en_text = (
    "The quick brown fox jumps over the lazy dog. "
    "Today is a beautiful sunny day. "
    "I am testing a voice to text application to see how accurate it is. "
    "Speech recognition technology has improved significantly in recent years. "
    "Machine learning models can now understand many languages and accents. "
    "Let us see how well this transcription works. "
    "Artificial intelligence is transforming the way we interact with computers. "
    "Thank you for watching this demonstration."
)

# Chinese test text
zh_text = (
    "你好，这是一个语音转文字的测试。"
    "今天天气很好，阳光明媚。"
    "我在测试语音识别的准确率，看看转换效果如何。"
    "科技改变生活，人工智能正在快速发展。"
    "希望这个工具能帮助你提高工作效率。"
    "谢谢你的使用。"
)

# Find English and Chinese voices
en_voice = None
zh_voice = None
for v in voices:
    name_lower = v.name.lower()
    if "english" in name_lower or "david" in name_lower or "zira" in name_lower or "mark" in name_lower:
        if en_voice is None:
            en_voice = v
    if "chinese" in name_lower or "huihui" in name_lower or "yaoyao" in name_lower or "hanhan" in name_lower:
        if zh_voice is None:
            zh_voice = v

# Generate English test file
print("\nGenerating English test audio...")
if en_voice:
    engine.setProperty("voice", en_voice.id)
    print(f"  Using voice: {en_voice.name}")
else:
    print("  No specific English voice found, using default")

engine.setProperty("rate", 150)  # speed
en_path = os.path.join(OUTPUT_DIR, "test_english.wav")
engine.save_to_file(en_text, en_path)
engine.runAndWait()
print(f"  Saved: {en_path}")

# Generate Chinese test file (if voice available)
zh_path = None
if zh_voice:
    print("\nGenerating Chinese test audio...")
    engine.setProperty("voice", zh_voice.id)
    print(f"  Using voice: {zh_voice.name}")
    engine.setProperty("rate", 150)
    zh_path = os.path.join(OUTPUT_DIR, "test_chinese.wav")
    engine.save_to_file(zh_text, zh_path)
    engine.runAndWait()
    print(f"  Saved: {zh_path}")
else:
    print("\nNo Chinese TTS voice found on this system. Skipping Chinese test.")

# Save ground truth
truth_path = os.path.join(OUTPUT_DIR, "test_ground_truth.txt")
with open(truth_path, "w", encoding="utf-8") as f:
    f.write("=== English Test (test_english.wav) ===\n")
    f.write(en_text + "\n\n")
    if zh_path:
        f.write("=== Chinese Test (test_chinese.wav) ===\n")
        f.write(zh_text + "\n")
print(f"\nGround truth saved: {truth_path}")

# Print file sizes
print("\n--- Generated files ---")
for name in ["test_english.wav", "test_chinese.wav", "test_ground_truth.txt"]:
    p = os.path.join(OUTPUT_DIR, name)
    if os.path.exists(p):
        size_kb = os.path.getsize(p) / 1024
        print(f"  {name}: {size_kb:.1f} KB")
