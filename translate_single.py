import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from ocr import create_gemini_client, translate_text_gemini

def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_single.py <filepath> <model>")
        return
        
    filepath = Path(sys.argv[1])
    model = sys.argv[2]
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
        
    prompt_file = Path("prompt.txt")
    prompt_text = prompt_file.read_text(encoding="utf-8").strip() if prompt_file.exists() else "Dịch sang tiếng Việt."
    
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    client = create_gemini_client(api_key)
    
    original_text = filepath.read_text(encoding="utf-8")
    print(f"Translating {filepath.name} with model {model}...")
    
    try:
        translated_text = translate_text_gemini(
            client=client,
            text=original_text,
            model=model,
            prompt=prompt_text
        )
        out_path = filepath.with_name(filepath.name.replace("_Cleaned.txt", "_Vietnamese_LN.txt"))
        out_path.write_text(translated_text, encoding="utf-8")
        print(f"Success! Saved to {out_path.name}")
    except Exception as e:
         print(f"Translation failed: {e}")

if __name__ == "__main__":
    main()
