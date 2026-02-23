import argparse
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Import utilities from out existing project files
from ocr import create_gemini_client, translate_text_gemini
from config import TRANSLATION_DELAY

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Batch translate text files in a directory using Gemini API.")
    parser.add_argument("--input-dir", required=True, help="Path to the directory containing text files")
    parser.add_argument("--prompt-file", default="prompt.txt", help="Path to the text file containing the translation prompt instructions")
    parser.add_argument("--input-suffix", default="_Cleaned.txt", help="Suffix of files to translate (e.g., _Cleaned.txt)")
    parser.add_argument("--output-suffix", default="_Vietnamese_LN.txt", help="Suffix for the translated output files")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="Gemini model to use for translation")
    parser.add_argument("--force", action="store_true", help="Force translation even if the output file already exists")
    parser.add_argument("--delay", type=float, default=TRANSLATION_DELAY, help="Delay in seconds between API calls to avoid rate limits")
    parser.add_argument("--glossary-file", type=str, default="glossary.txt", help="Path to an optional glossary file (e.g., glossary.txt) to enforce specific terminology")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Verification
    input_dir = Path(args.input_dir)
    i_suffix = args.input_suffix
    o_suffix = args.output_suffix
    
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory not found: {input_dir}")
        return
        
    prompt_file = Path(args.prompt_file)
    if not prompt_file.exists():
        logger.error(f"Prompt file not found: {prompt_file}. Please create it and add your translation instructions.")
        return
        
    prompt_text = prompt_file.read_text(encoding="utf-8").strip()
    if not prompt_text:
        logger.error(f"Prompt file is empty: {prompt_file}")
        return
        
    glossary_text = ""
    glossary_path = Path(args.glossary_file)
    if glossary_path.exists():
        glossary_text = glossary_path.read_text(encoding="utf-8").strip()
        if glossary_text:
            logger.info(f"Loaded glossary from {glossary_path.name}")
        
    # 2. Find Files
    target_files = sorted(list(input_dir.glob(f"*{i_suffix}")))
    if not target_files:
        logger.info(f"No files ending with '{i_suffix}' found in {input_dir}")
        return
        
    logger.info(f"Found {len(target_files)} file(s) to process.")
    
    # 3. Setup Gemini
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
         logger.error("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
         return
         
    client = create_gemini_client(api_key)
    if not client:
        return
    
    # 4. Translation Loop
    success_count = 0
    skip_count = 0
    previous_context = "" # Rolling context from previous chapter
    
    for i, file_path in enumerate(target_files, 1):
        filename = file_path.name
        logger.info(f"Processing ({i}/{len(target_files)}): {filename}")
        
        # Calculate Output Path
        out_filename = filename.replace(i_suffix, o_suffix)
        out_path = input_dir / out_filename
        
        # Skip existing?
        if out_path.exists() and not args.force:
            logger.info(f"  -> File {out_filename} already exists. Skipping.")
            skip_count += 1
            # Update rolling context even if skipping, so the next chapter has the correct context
            try:
                original_text = file_path.read_text(encoding="utf-8")
                previous_context = original_text[-1500:] if len(original_text) > 1500 else original_text
            except:
                pass
            continue
            
        # Read Original Text
        original_text = file_path.read_text(encoding="utf-8")
        if not original_text.strip():
            logger.warning(f"  -> File is empty. Skipping.")
            continue
            
        logger.debug(f"  -> Sending {len(original_text)} chars to Gemini ({args.model})...")
        
        # Construct dynamic prompt
        dynamic_prompt = prompt_text
        if glossary_text:
            dynamic_prompt += f"\n\n[TỪ ĐIỂN THUẬT NGỮ / GLOSSARY]\nHãy BẮT BUỘC sử dụng các thuật ngữ sau khi dịch:\n{glossary_text}"
        if previous_context:
            dynamic_prompt += f"\n\n[BỐI CẢNH TỪ CHƯƠNG TRƯỚC / PREVIOUS CHAPTER CONTEXT]\nĐây là phần cuối của chương trước để bạn nắm bắt bối cảnh và mạch truyện. KHÔNG DỊCH phần này:\n...\n{previous_context}"
        
        try:
            # Perform Translation
            translated_text = translate_text_gemini(
                client=client,
                text=original_text,
                model=args.model,
                prompt=dynamic_prompt
            )
            
            # Save Output
            out_path.write_text(translated_text, encoding="utf-8")
            logger.info(f"  -> Saved translation: {out_filename}")
            success_count += 1
            
            # Update rolling context for next iteration
            previous_context = original_text[-1500:] if len(original_text) > 1500 else original_text
            
        except Exception as e:
            logger.error(f"  -> Translation failed for {filename}: {e}")
            
        # Cooldown unless it's the very last iteration
        if i < len(target_files):
            logger.info(f"  -> Cooldown for {args.delay} seconds to respect API limits...")
            time.sleep(args.delay)
            
    logger.info("====================================")        
    logger.info(f"Completed! Translated: {success_count} | Skipped: {skip_count} | Total: {len(target_files)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Translation stopped by user.")
