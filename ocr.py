"""Local OCR + Gemini Refinement pipeline."""

import logging
import io
import time
import re
import easyocr
import numpy as np
from PIL import Image, ImageEnhance
from google import genai
from google.genai import types
from config import OCR_LANGUAGES

logger = logging.getLogger(__name__)

# ... (EasyOCR and preprocess_image functions remain unchanged) ...

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        logger.info(f"Initializing EasyOCR with languages: {OCR_LANGUAGES}...")
        _reader = easyocr.Reader(OCR_LANGUAGES)
    return _reader

def create_gemini_client(api_key: str) -> genai.Client:
    """Initialize the Gemini API client."""
    return genai.Client(api_key=api_key)

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Convert bytes to numpy array with scaling and contrast enhancement."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # 1. Scale up by 2x to improve OCR accuracy on small text
        new_size = (image.width * 2, image.height * 2)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # 2. Convert to grayscale
        image = image.convert("L")
        
        # 3. Increase contrast (moderate)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Convert to numpy array for EasyOCR
        return np.array(image)
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return None

def extract_raw_text_local(segment_bytes: bytes) -> str:
    """Extract raw text from a screenshot segment using EasyOCR."""
    reader = get_reader()
    
    # Preprocess
    img_array = preprocess_image(segment_bytes)
    if img_array is None:
        return ""

    # Run OCR
    # detail=0 returns just the list of text strings
    try:
        results = reader.readtext(img_array, detail=0, paragraph=True)
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Local OCR failed: {e}")
        return ""

def generate_with_retry(client, model, contents, config=None):
    """Wraps model.generate_content with strict 429/Quota retry logic."""
    max_retries = 10
    attempt = 0
    
    while attempt < max_retries:
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                attempt += 1
                
                # Extract wait time
                wait_time = 60 # Default
                match = re.search(r"retry in (\d+(\.\d+)?)s", error_str)
                if match:
                    wait_time = float(match.group(1)) + 1 # Add 1s buffer
                
                logger.warning(f"Rate limited (429). Waiting {wait_time:.1f}s before retry {attempt}/{max_retries}...")
                time.sleep(wait_time)
            else:
                raise e
    
    raise RuntimeError("Max retries exceeded for Gemini API.")

def refine_text_gemini(
    client: genai.Client,
    raw_text: str,
    model: str,
    prompt: str,
) -> str:
    """Send raw OCR text to Gemini for cleanup/refinement."""
    if not raw_text or len(raw_text.strip()) < 10:
        return "[NO TEXT]"

    try:
        response = generate_with_retry(
            client=client,
            model=model,
            contents=[prompt, f"\n\n--- RAW TEXT START ---\n{raw_text}\n--- RAW TEXT END ---"]
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini refinement failed: {e}")
        return raw_text  # Fallback to raw text on error

def translate_text_gemini(
    client: genai.Client,
    text: str,
    model: str,
    prompt: str,
) -> str:
    """Send cleaned English text to Gemini for translation."""
    if not text or len(text.strip()) < 10:
        return "[NO TEXT]"

    try:
        # Disable safety filters to prevent false positives on novel content
        response = generate_with_retry(
            client=client,
            model=model,
            contents=[prompt, f"\n\n--- ENGLISH TEXT START ---\n{text}\n--- ENGLISH TEXT END ---"],
            config=types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                ]
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        return f"[TRANSLATION FAILED: {str(e)}]"

def extract_text_hybrid(
    client: genai.Client,
    screenshot_segments: list[bytes],
    model: str,
    prompt: str,
) -> str:
    """Full pipeline: Local OCR -> Concatenate -> Gemini Refine."""
    
    # 1. Local OCR on all segments
    raw_parts = []
    for i, segment in enumerate(screenshot_segments):
        logger.info(f"    Local OCR segment {i + 1}/{len(screenshot_segments)}...")
        text = extract_raw_text_local(segment)
        if text:
            raw_parts.append(text)
    
    full_raw_text = "\n\n".join(raw_parts)
    
    if not full_raw_text.strip():
        return "[NO TEXT]"
    
    logger.info(f"    Raw text extracted ({len(full_raw_text)} chars). Sending to Gemini for refinement...")
    
    # 2. Gemini Refinement
    refined_text = refine_text_gemini(client, full_raw_text, model, prompt)
    
    return refined_text
