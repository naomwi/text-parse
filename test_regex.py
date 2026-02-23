import re

text = """
# 4 - Frail (Not Really)

After the commotion of the previous day, the butler realized something.
"""

# Let's test the current regex
lines = text.strip().split('\n')[:5]
for line in lines:
    line = line.strip()
    match = re.search(r"^(?:#\s*)?(?:Ch\.|Chapter\s*)?(\d+)(?:\s*-|\s*:|\s*$|[^a-zA-Z0-9])", line, re.IGNORECASE)
    print(f"Line: {repr(line)}")
    if match:
        print(f"  MATCH: {match.group(1)}")
    else:
        print("  NO MATCH")
