# transcribe.py

import os
import whisper

from pathlib import Path

# CONFIG

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "interview"
OUTPUT_DIR = ROOT / "transcripts"
MODEL_SIZE = "small"
LANGUAGE = "Japanese"
TASK = "transcribe"
FILE_EXTENSION = ".m4a"

# FUNCTIONS

def clear_screen():
    """
    Clear the console screen.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def load_model(model_size):
    """
    Load and return the Whisper model.
    """
    return whisper.load_model(model_size)

def setup_output_directory(output_dir):
    """
    Create the output directory if it doesn't exist.
    """
    if not os.path.exists(output_dir):
        output_dir.mkdir(exist_ok=True, parents=True)

def transcribe_file(model, input_path, output_path, language, task="transcribe"):
    """
    Transcribe with segment information for better formatting.
    
    @model: Whisper model instance
    @input_path: Path to the input audio file
    @output_path: Path to save the transcription output
    @language: Language of the audio file
    @task: Either "transcribe" (default) or "translate"
    """
    try:
        print(f"Transcribing: {input_path.name}")
        result = model.transcribe(
            str(input_path), 
            language=language, 
            task=task,
            verbose=True
        )
        
        print(f"\nFound {len(result['segments'])} segments")
        
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"]):
                timestamp = f"[{segment['start']:.1f}s]"
                text = segment['text'].strip()
                f.write(f"{timestamp} {text}\n\n")
        
        print(f"Saved: {output_path}")
        return True
    except Exception as e:
        print(f"\nError processing {input_path}: {str(e)}")
        return False

def process_directory(model, input_dir, output_dir, language, file_extension):
    """
    Process all audio files in the input directory.
    """
    file_no = 0
    total_files = len(list(input_dir.glob(f"*{file_extension}")))
    
    for file_path in input_dir.glob(f"*{file_extension}"):
        file_no += 1
        print(f"\nProcessing file: {file_no}/{total_files}")
        output_path = output_dir / f"{file_path.stem}.txt"
        transcribe_file(model, file_path, output_path, language)

# MAIN FUNCTION

def main():
    """
    Main function.
    """
    model = load_model(MODEL_SIZE)
    setup_output_directory(OUTPUT_DIR)
    
    print("=== Whisper Transcriber Started ===\n")
    print(f"Input Directory  : {INPUT_DIR}")
    print(f"Output Directory : {OUTPUT_DIR}")
    print(f"Model Size       : {MODEL_SIZE}")
    print(f"Language         : {LANGUAGE}")
    print(f"Task             : {TASK}")
    print(f"File Extension   : {FILE_EXTENSION}")
    
    process_directory(model, INPUT_DIR, OUTPUT_DIR, LANGUAGE, FILE_EXTENSION)
    
    print("\n=== Whisper Transcriber Completed ===")

if __name__ == "__main__":
    clear_screen()
    main()