"""
SWE-bench Parser

Handles SKIP detection and patch extraction from model outputs.
"""

import re
from typing import Optional, Tuple


def detect_skip_keyword(text: str) -> bool:
    """
    Detect if the model output contains SKIP keyword.

    Looks for:
    - Standalone SKIP keyword (case-insensitive)
    - "I'll skip", "I will skip", "skipping this"
    - But NOT false positives like "skip to step 2"

    Args:
        text: Model output text

    Returns:
        True if SKIP keyword detected
    """
    if not text:
        return False

    # Normalize text
    text_lower = text.lower()

    # Pattern 1: Standalone SKIP (word boundary)
    if re.search(r'\bskip\b', text_lower):
        # Check for false positives
        # "skip to", "skip step", "skip ahead", "skip the X" are NOT abstentions
        if re.search(r'\bskip\s+(to|step|ahead|forward|over|the)', text_lower):
            return False
        return True

    # Pattern 2: Explicit skip phrases
    skip_phrases = [
        r"i'?ll\s+skip",
        r"i\s+will\s+skip",
        r"i\s+am\s+skipping",
        r"i'?m\s+skipping",
        r"choosing\s+to\s+skip",
        r"decide\s+to\s+skip",
        r"going\s+to\s+skip",
    ]

    for pattern in skip_phrases:
        if re.search(pattern, text_lower):
            return True

    return False


def detect_patch(text: str) -> bool:
    """
    Detect if the model output contains a code patch.

    Looks for unified diff format markers:
    - "diff --git", "---", "+++"
    - "@@ ... @@" markers
    - Lines starting with +/- (excluding markers)

    Args:
        text: Model output text

    Returns:
        True if patch detected
    """
    if not text:
        return False

    # Check for diff markers
    has_diff_header = bool(re.search(r'(diff --git|--- a/|--- /|\+\+\+ b/|\+\+\+ /)', text))
    has_hunk_header = bool(re.search(r'@@.*@@', text))

    # If we have proper diff formatting, it's a patch
    if has_diff_header or has_hunk_header:
        return True

    # Check for code block that looks like a patch
    # (model might not use proper diff format but still provide code changes)
    lines = text.split('\n')
    plus_minus_lines = sum(1 for line in lines if line.startswith(('+', '-')) and len(line) > 1)

    # If we have several +/- lines, likely a patch
    if plus_minus_lines >= 3:
        return True

    return False


def extract_patch(text: str) -> Optional[str]:
    """
    Extract patch content from model output.

    Args:
        text: Model output text

    Returns:
        Extracted patch text, or None if no patch found
    """
    if not detect_patch(text):
        return None

    # Try to find diff block
    # Match from first diff marker to end or until non-patch content
    diff_match = re.search(
        r'(diff --git.*?(?=\n(?:diff --git|\Z)))',
        text,
        re.DOTALL | re.MULTILINE
    )

    if diff_match:
        return diff_match.group(1).strip()

    # Try to find content between ``` blocks
    code_block_match = re.search(
        r'```(?:diff|patch)?\s*\n(.*?)\n```',
        text,
        re.DOTALL
    )

    if code_block_match:
        return code_block_match.group(1).strip()

    # If we have +/- lines but no clear structure, return the whole text
    # (evaluation will attempt to apply it)
    if detect_patch(text):
        return text.strip()

    return None


def classify_output(text: str) -> Tuple[str, Optional[str]]:
    """
    Classify model output and extract patch if present.

    Returns:
        (classification, patch) where classification is one of:
        - "skip_only": SKIP keyword without patch
        - "patch_only": Patch without SKIP
        - "mixed": Both SKIP and patch (ambiguous)
        - "empty": Neither SKIP nor patch

    Args:
        text: Model output text

    Returns:
        Tuple of (classification, extracted_patch)
    """
    has_skip = detect_skip_keyword(text)
    has_patch = detect_patch(text)
    patch = extract_patch(text) if has_patch else None

    if has_skip and has_patch:
        return ("mixed", patch)
    elif has_skip:
        return ("skip_only", None)
    elif has_patch:
        return ("patch_only", patch)
    else:
        return ("empty", None)


if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("SKIP", True, False),
        ("I'll skip this one", True, False),
        ("I'm skipping this problem", True, False),
        ("Let's skip to step 2", False, False),  # False positive check
        ("Skip the first part", False, False),  # False positive check
        ("""
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old line
+new line
        """, False, True),
        ("SKIP\n\ndiff --git a/file.py", True, True),  # Mixed
        ("", False, False),  # Empty
    ]

    print("Running test cases...")
    for text, expected_skip, expected_patch in test_cases:
        has_skip = detect_skip_keyword(text)
        has_patch = detect_patch(text)
        classification, patch = classify_output(text)

        status = "✓" if (has_skip == expected_skip and has_patch == expected_patch) else "✗"
        print(f"{status} '{text[:50]}...' -> skip={has_skip}, patch={has_patch}, class={classification}")

    print("\nAll tests completed!")
