#!/usr/bin/env python3
"""
Fetch definitions and etymologies for words missing them in the word-data JSON files.
Uses the Free Dictionary API: https://dictionaryapi.dev/
"""

import json
import time
import urllib.request
import urllib.error
import os
import sys
from pathlib import Path

# API endpoint
API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

# Rate limiting - be nice to the free API
REQUESTS_PER_SECOND = 2
DELAY_BETWEEN_REQUESTS = 1.0 / REQUESTS_PER_SECOND

# Progress file to allow resuming
PROGRESS_FILE = "fetch_definitions_progress.json"

def load_progress():
    """Load progress from file to allow resuming."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"completed": {}, "failed": {}}

def save_progress(progress):
    """Save progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def fetch_definition(word):
    """Fetch definition and etymology from the API."""
    try:
        url = API_URL.format(word=word.lower())
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (word-puzzle-games definition fetcher)'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                return None, None, f"http_{response.status}"
            
            data = json.loads(response.read().decode('utf-8'))
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None, None, "empty_response"
        
        entry = data[0]
        
        # Extract definition
        definition = ""
        if entry.get("meanings"):
            for meaning in entry["meanings"]:
                if meaning.get("definitions"):
                    part_of_speech = meaning.get("partOfSpeech", "")
                    first_def = meaning["definitions"][0].get("definition", "")
                    if first_def:
                        definition = f"({part_of_speech}) {first_def}" if part_of_speech else first_def
                        break
        
        # Extract etymology
        etymology = ""
        if entry.get("origin"):
            etymology = entry["origin"]
        
        return definition, etymology, "success"
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None, "not_found"
        return None, None, f"http_{e.code}"
    except urllib.error.URLError as e:
        return None, None, f"url_error: {str(e)}"
    except json.JSONDecodeError:
        return None, None, "json_error"
    except Exception as e:
        return None, None, f"error: {str(e)}"

def process_word_file(filepath, progress):
    """Process a single word file, fetching missing definitions."""
    print(f"\n{'='*60}")
    print(f"Processing: {filepath}")
    print(f"{'='*60}")
    
    # Load the word data
    with open(filepath, 'r') as f:
        word_data = json.load(f)
    
    filename = os.path.basename(filepath)
    
    # Initialize progress for this file if not exists
    if filename not in progress["completed"]:
        progress["completed"][filename] = []
    if filename not in progress["failed"]:
        progress["failed"][filename] = {}
    
    # Find words that need definitions
    words_needing_defs = []
    for word, info in word_data.items():
        # Skip if already has definition or is a derived form with base
        if info.get("d") or info.get("base"):
            continue
        # Skip if already processed
        if word in progress["completed"][filename]:
            continue
        if word in progress["failed"][filename]:
            continue
        words_needing_defs.append(word)
    
    total_words = len(words_needing_defs)
    print(f"Words needing definitions: {total_words}")
    
    if total_words == 0:
        print("No words to process!")
        return word_data, 0, 0
    
    success_count = 0
    fail_count = 0
    modified = False
    
    for i, word in enumerate(words_needing_defs):
        # Progress indicator
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{total_words}] Processing {word}...", end="", flush=True)
        
        definition, etymology, status = fetch_definition(word)
        
        if status == "success" and (definition or etymology):
            word_data[word]["d"] = definition or ""
            word_data[word]["e"] = etymology or ""
            progress["completed"][filename].append(word)
            success_count += 1
            modified = True
            if (i + 1) % 10 == 0:
                print(f" ✓ got definition")
        else:
            progress["failed"][filename][word] = status
            fail_count += 1
            if (i + 1) % 10 == 0:
                print(f" ✗ {status}")
        
        # Save progress periodically
        if (i + 1) % 50 == 0:
            save_progress(progress)
            # Also save the word data periodically
            if modified:
                with open(filepath, 'w') as f:
                    json.dump(word_data, f, separators=(',', ':'))
                print(f"  [Saved progress: {success_count} new definitions]")
        
        # Rate limiting
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Final save
    save_progress(progress)
    if modified:
        with open(filepath, 'w') as f:
            json.dump(word_data, f, separators=(',', ':'))
    
    print(f"\nCompleted {filename}: {success_count} definitions added, {fail_count} failed")
    return word_data, success_count, fail_count

def main():
    """Main function to process all word files."""
    word_files = [
        "word-data/words3.json",
        "word-data/words4.json", 
        "word-data/words5.json",
        "word-data/words6.json",
        "word-data/words7.json",
    ]
    
    # Check which files exist
    existing_files = [f for f in word_files if os.path.exists(f)]
    
    if not existing_files:
        print("No word files found!")
        return
    
    print("=" * 60)
    print("Word Definition Fetcher")
    print("=" * 60)
    print(f"Found {len(existing_files)} word files to process")
    print("This will take a while due to API rate limiting...")
    print("You can stop and resume at any time (progress is saved)")
    print()
    
    # Load progress
    progress = load_progress()
    
    total_success = 0
    total_fail = 0
    
    for filepath in existing_files:
        try:
            _, success, fail = process_word_file(filepath, progress)
            total_success += success
            total_fail += fail
        except KeyboardInterrupt:
            print("\n\nInterrupted! Progress has been saved.")
            print("Run the script again to resume.")
            sys.exit(0)
        except Exception as e:
            print(f"\nError processing {filepath}: {e}")
            continue
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total definitions added: {total_success}")
    print(f"Total failed lookups: {total_fail}")
    print(f"\nProgress saved to: {PROGRESS_FILE}")
    print("Run again to retry failed words or process new files.")

if __name__ == "__main__":
    main()
