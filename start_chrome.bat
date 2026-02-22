@echo off
echo Starting Chrome for Automation...
echo User Data Directory: C:\ChromeDev
echo Remote Debugging Port: 9222

mkdir C:\ChromeDev 2>nul

"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDev" --no-first-run --no-default-browser-check

echo Chrome started. You can now run "python main.py --mode cdp"
pause
