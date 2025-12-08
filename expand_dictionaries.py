#!/usr/bin/env python3
"""
Script to expand word dictionaries with plurals, past tense, and other word forms.
For derived words (plurals, past tense, etc.), it stores the base word's definition
directly so the game doesn't need to look up multiple dictionaries.

The definition is prefixed with the relation (e.g., "Plural of WORD: [definition]")
"""

import json
import urllib.request
import re
from pathlib import Path

WORD_DATA_DIR = Path(__file__).parent / "word-data"

# URLs for comprehensive word lists
DWYL_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"

# Common word form patterns - order matters (more specific first)
# These are designed to be conservative to avoid false positives

PLURAL_PATTERNS = [
    (r'^(.+)ies$', r'\1y'),      # babies -> baby
    (r'^(.+)ves$', r'\1f'),      # wolves -> wolf
    (r'^(.+)ves$', r'\1fe'),     # wives -> wife
    (r'^(.+[sxz])es$', r'\1'),   # boxes -> box
    (r'^(.+[cs]h)es$', r'\1'),   # churches -> church
    (r'^(.+)s$', r'\1'),         # cats -> cat (not es - too many false positives)
]

PAST_TENSE_PATTERNS = [
    (r'^(.+)ied$', r'\1y'),      # carried -> carry
    (r'^(.+)([^aeiou])\2ed$', r'\1\2'),  # stopped -> stop
    (r'^(.+[^e])ed$', r'\1e'),   # loved -> love (only if not already ending in e)
    (r'^(.+)ed$', r'\1'),        # walked -> walk
]

PRESENT_PARTICIPLE_PATTERNS = [
    (r'^(.+)ying$', r'\1y'),     # carrying -> carry  
    (r'^(.+)([^aeiou])\2ing$', r'\1\2'),  # stopping -> stop
    (r'^(.+)ing$', r'\1e'),      # loving -> love
    (r'^(.+)ing$', r'\1'),       # walking -> walk
]

# Be very conservative with comparative/superlative - many words ending in -er/-est are NOT comparatives
COMPARATIVE_PATTERNS = [
    (r'^(.+)ier$', r'\1y'),      # happier -> happy
    (r'^(.+)([^aeiou])\2er$', r'\1\2'),  # bigger -> big (doubled consonant only)
]

SUPERLATIVE_PATTERNS = [
    (r'^(.+)iest$', r'\1y'),     # happiest -> happy
    (r'^(.+)([^aeiou])\2est$', r'\1\2'),  # biggest -> big (doubled consonant only)
]

ALL_PATTERNS = [
    ('Plural of', PLURAL_PATTERNS),
    ('Past tense of', PAST_TENSE_PATTERNS),
    ('Present participle of', PRESENT_PARTICIPLE_PATTERNS),
    ('Comparative form of', COMPARATIVE_PATTERNS),
    ('Superlative form of', SUPERLATIVE_PATTERNS),
]


def download_words():
    """Download comprehensive word list."""
    print(f"Downloading word list from {DWYL_URL}...")
    try:
        with urllib.request.urlopen(DWYL_URL) as response:
            content = response.read().decode('utf-8')
            words = {line.strip().upper() for line in content.split('\n') if line.strip() and line.strip().isalpha()}
            print(f"Downloaded {len(words)} words")
            return words
    except Exception as e:
        print(f"Error downloading: {e}")
        return set()


def find_base_word(word, all_dictionaries, all_words):
    """
    Try to find the base word for a derived form.
    Returns (base_word, relation, base_info) or (None, None, None).
    """
    word_lower = word.lower()
    
    for relation, patterns in ALL_PATTERNS:
        for pattern, replacement in patterns:
            match = re.match(pattern, word_lower)
            if match:
                base = re.sub(pattern, replacement, word_lower).upper()
                # Check if base word exists
                if base in all_words and len(base) < len(word):
                    # Try to find base word info in dictionaries
                    for length, data in all_dictionaries.items():
                        if base in data:
                            base_info = data[base]
                            # Only use if base has a real definition
                            if base_info.get('d') and len(base_info['d']) > 5:
                                # Don't use if base is itself a reference
                                if not base_info.get('base'):
                                    return base, relation, base_info
                    # Base exists but no definition found
                    return base, relation, None
    
    return None, None, None


def load_existing_wordlist(length):
    """Load existing word list JSON file."""
    filepath = WORD_DATA_DIR / f"words{length}.json"
    if not filepath.exists():
        return {}
    
    with open(filepath, 'r') as f:
        return json.load(f)


def save_wordlist(length, data):
    """Save word list JSON file."""
    filepath = WORD_DATA_DIR / f"words{length}.json"
    # Sort by key for consistent output
    sorted_data = dict(sorted(data.items()))
    with open(filepath, 'w') as f:
        json.dump(sorted_data, f, separators=(',', ':'))
    print(f"Saved {len(data)} words to {filepath}")


def main():
    print("Word Dictionary Expansion Script")
    print("=" * 50)
    
    # Download comprehensive word list
    all_words = download_words()
    
    if not all_words:
        print("Failed to download words. Exiting.")
        return
    
    # Load all existing dictionaries first
    print("\nLoading existing dictionaries...")
    all_dictionaries = {}
    for length in range(3, 8):
        data = load_existing_wordlist(length)
        all_dictionaries[length] = data
        print(f"  words{length}.json: {len(data)} words")
    
    # Process each word length
    print("\nExpanding dictionaries...")
    for length in range(3, 8):
        print(f"\nProcessing {length}-letter words...")
        
        # Filter downloaded words to this length
        length_words = {w for w in all_words if len(w) == length}
        
        # Start with existing data
        data = dict(all_dictionaries[length])
        
        added = 0
        derived_with_def = 0
        derived_without_def = 0
        
        for word in sorted(length_words):
            if word in data:
                # Update existing entry if it's derived but missing base definition
                info = data[word]
                if info.get('base') and info.get('d', '').startswith(('Plural of', 'Past tense of', 'Present participle of', 'Comparative form of', 'Superlative form of')):
                    # Already processed
                    continue
                    
                # Check if current definition is just a placeholder
                if not info.get('d') or len(info['d']) < 10:
                    base, relation, base_info = find_base_word(word, all_dictionaries, all_words)
                    if base and base_info and base_info.get('d'):
                        data[word] = {
                            'd': f"{relation} {base}: {base_info['d']}",
                            'e': base_info.get('e', ''),
                            'base': base,
                            'relation': relation
                        }
                        derived_with_def += 1
                continue
            
            # New word
            base, relation, base_info = find_base_word(word, all_dictionaries, all_words)
            
            if base:
                if base_info and base_info.get('d'):
                    # Derived word with base definition available
                    data[word] = {
                        'd': f"{relation} {base}: {base_info['d']}",
                        'e': base_info.get('e', ''),
                        'base': base,
                        'relation': relation
                    }
                    derived_with_def += 1
                else:
                    # Derived word but no base definition
                    data[word] = {
                        'd': f"{relation} {base}.",
                        'e': '',
                        'base': base,
                        'relation': relation
                    }
                    derived_without_def += 1
            else:
                # Not a derived word, add with empty definition
                data[word] = {'d': '', 'e': ''}
            
            added += 1
        
        print(f"  Added {added} new words")
        print(f"  {derived_with_def} derived words with definitions")
        print(f"  {derived_without_def} derived words without definitions")
        
        # Update our reference
        all_dictionaries[length] = data
        
        # Save
        save_wordlist(length, data)
    
    print("\n" + "=" * 50)
    print("Done! Dictionaries expanded with derived word forms.")
    print("Derived words now include their base word's definition.")


if __name__ == "__main__":
    main()
