# AI Novel Extractor & Translator

*[Đọc bằng tiếng Việt (Read in Vietnamese)](README_vi.md)*
A Python-based desktop application for extracting, cleaning, and automatically translating Light Novels and web serials from popular platforms directly into your native language using Google's Gemini AI.

## Supported Platforms

*   **Novelpia Global** (`global.novelpia.com/viewer/...`)
*   **Novelpia Main** (`novelpia.com/viewer/...`) - Automatically bypasses hidden base64 anti-scraping tags!
*   **Pixiv Novels** (`pixiv.net/novel/show.php?id=...`) - Extracts pristine text via Pixiv's internal AJAX API.
*   **Pixiv Series** (`pixiv.net/novel/series/...`) - Automatically fetches the entire episode list and downloads the whole series in order!

## Prerequisites

1.  **Google Chrome** installed on your Windows PC.
2.  **Google Gemini API Key**: You need a free API key from [Google AI Studio](https://aistudio.google.com/).
    *   *Note: If you use the free tier, the script may occasionally pause for 60 seconds if you extract chapters too quickly to respect rate limits.*

## Initial Setup

1.  **Extract the files** to a folder on your computer.
2.  **Add your API Key**:
    *   Open the `.env` file in Notepad (create one if it doesn't exist by renaming `.env.example`).
    *   Paste your key so it looks like this: `GEMINI_API_KEY="AIzaSyYourKeyHere..."`
3.  **Install & Run**:
    *   Double-click the **`Start_GUI.bat`** file.
    *   The first time it runs, it will auto-install Python requirements and Playwright browsers (this takes a minute).
    *   It will then launch the graphical interface!

## How to Use

1.  **Launch the App**: Double-click **`Start_GUI.bat`**.
2.  **Fill in the fields**:
    *   **Start URL**: Paste the link to the FIRST chapter you want to grab.
        *   *For Pixiv Series*: Paste the series URL (e.g., `https://www.pixiv.net/novel/series/15160863`) to download all available chapters automatically.
    *   **Max Chapters**: How many chapters to download before stopping.
    *   **Translation Toggle**: Turn it ON to generate a second Vietnamese localized text file alongside the original Japanese/Korean file!
3.  **Click Start**!

### The First Time You Run It...
A Google Chrome window will pop up. **You must quickly log in to Novelpia or Pixiv in this window** so the script has access to your session (especially for R-18 and paid content).
Once logged in, the script will automatically capture your cookies and handle the rest in the background!

## Output Files

Check your `output/` folder! For every chapter, you will get:
*   `Chapter_001_ChapterTitle_id1234_Cleaned.txt` - The raw, formatted original text.
*   `Chapter_001_ChapterTitle_id1234_Vietnamese_LN.txt` (If translation is enabled).

## Troubleshooting

*   **"Gemini Rate Limit Hit"**: The Free Tier of Gemini only allows a certain number of requests per minute. The script will automatically pause for 60 seconds and resume. Add a payment method to Google AI if you want instant, limitless extractions.
*   **Chrome closes immediately**: Ensure all your normal Chrome windows are closed before starting the extractor, as it needs to attach a debugging profile to the browser!
*   **Nothing is extracting from Pixiv**: Ensure your Pixiv account has the "Show R-18 Content" toggle enabled in your profile settings if you are trying to grab age-restricted works.
