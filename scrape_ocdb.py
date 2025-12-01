#!/usr/bin/env python3
"""
Only Connect Database (OCDB) Scraper

Extracts episode information from https://ocdb.cc including:
- Episode titles and metadata (series, episode number)
- Round 1 & 2: Connection rounds with clues and answers
- Round 3: Connecting Wall
- Round 4: Missing Vowels

Downloads gently with exponential backoff on errors.
Saves data in JSON format.
"""

import json
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import urljoin
from html import unescape

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://ocdb.cc"
EPISODES_URL = f"{BASE_URL}/episodes/"
OUTPUT_FILE = "only_connect_episodes.json"
PROGRESS_FILE = "scrape_progress.json"

# Rate limiting
MIN_DELAY = 1.5  # Minimum seconds between requests
MAX_DELAY = 3.0  # Maximum seconds between requests
BACKOFF_FACTOR = 2  # Exponential backoff multiplier
MAX_RETRIES = 5  # Maximum retry attempts

# Greek letter indices (early episodes)
GREEK_LETTERS = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta']
GREEK_SYMBOLS = ['𝝰', '𝝱', '𝝲', '𝝳', '𝝴', '𝝵']

# Egyptian hieroglyph indices (later episodes)
EGYPTIAN_GLYPHS = [
    'Two Reeds', 'Horned Viper', 'Lion', 'Water', 'Twisted Flax', 'Eye of Horus'
]


class RateLimiter:
    """Handles rate limiting with exponential backoff."""
    
    def __init__(self):
        self.delay = MIN_DELAY
        self.last_request = 0
        
    def wait(self):
        """Wait before next request."""
        elapsed = time.time() - self.last_request
        wait_time = max(0, self.delay - elapsed)
        if wait_time > 0:
            # Add small random jitter
            jitter = random.uniform(0, 0.5)
            time.sleep(wait_time + jitter)
        self.last_request = time.time()
        
    def success(self):
        """Call on successful request to reduce delay."""
        self.delay = max(MIN_DELAY, self.delay * 0.9)
        
    def failure(self):
        """Call on failed request to increase delay."""
        self.delay = min(MAX_DELAY * 10, self.delay * BACKOFF_FACTOR)
        print(f"  Backing off, delay now {self.delay:.1f}s")


class OCDBScraper:
    """Scraper for the Only Connect Database."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OCDB Educational Scraper (gentle, rate-limited)',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-GB,en;q=0.9',
        })
        self.rate_limiter = RateLimiter()
        self.episodes = []
        self.progress = {'completed': [], 'failed': []}
        
    def load_progress(self):
        """Load progress from previous run."""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                self.progress = json.load(f)
            print(f"Loaded progress: {len(self.progress['completed'])} completed, "
                  f"{len(self.progress['failed'])} failed")
                  
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                self.episodes = json.load(f)
            print(f"Loaded {len(self.episodes)} existing episodes")
            
    def save_progress(self):
        """Save progress for resume capability."""
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2)
            
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.episodes, f, indent=2, ensure_ascii=False)
            
    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a page with rate limiting and retries."""
        for attempt in range(MAX_RETRIES):
            self.rate_limiter.wait()
            
            try:
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    self.rate_limiter.success()
                    return BeautifulSoup(response.text, 'html.parser')
                    
                elif response.status_code == 429:  # Too Many Requests
                    print(f"  Rate limited (429), backing off...")
                    self.rate_limiter.failure()
                    
                elif response.status_code >= 500:
                    print(f"  Server error ({response.status_code}), retrying...")
                    self.rate_limiter.failure()
                    
                else:
                    print(f"  HTTP {response.status_code} for {url}")
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"  Timeout, retrying...")
                self.rate_limiter.failure()
                
            except requests.exceptions.RequestException as e:
                print(f"  Request error: {e}")
                self.rate_limiter.failure()
                
        print(f"  Failed after {MAX_RETRIES} attempts")
        return None
        
    def get_episode_urls(self) -> list[dict]:
        """Get all episode URLs from the episodes page."""
        print("Fetching episode list...")
        soup = self.fetch_page(EPISODES_URL)
        
        if not soup:
            print("Failed to fetch episode list!")
            return []
            
        episodes = []
        current_series = None
        
        # Find the episode list container
        content = soup.find('div', class_='episode-list') or soup.find('div', class_='content')
        if not content:
            content = soup
            
        # Look for series headers and episode links
        for element in content.find_all(['h2', 'a']):
            if element.name == 'h2':
                # Series header like "Series 1" or "Series Specials"
                text = element.get_text(strip=True)
                if text.startswith('Series'):
                    current_series = text
                    
            elif element.name == 'a' and current_series:
                href = element.get('href', '')
                if '/episode/' in href:
                    title = element.get_text(strip=True)
                    # Extract episode number from title
                    ep_match = re.search(r'Episode\s*(\d+)', title)
                    ep_num = int(ep_match.group(1)) if ep_match else None
                    
                    # Clean up title
                    clean_title = re.sub(r'^Episode\s*\d+:\s*', '', title).strip()
                    
                    episodes.append({
                        'url': urljoin(BASE_URL, href),
                        'series': current_series,
                        'episode_number': ep_num,
                        'title': clean_title
                    })
                    
        print(f"Found {len(episodes)} episodes")
        return episodes
        
    def clean_text(self, element) -> str:
        """Extract clean text from an element."""
        if element is None:
            return ""
        text = element.get_text(separator=' ', strip=True)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
        
    def extract_clues(self, container) -> list[str]:
        """Extract clue text from a round container."""
        clues = []
        
        # Find all clue divs
        clue_divs = container.find_all('div', class_='clue')
        
        for clue_div in clue_divs:
            # Check for audio link (music clue)
            audio_link = clue_div.find('a', href=re.compile(r'\.mp3$'))
            if audio_link:
                clues.append({'type': 'audio', 'url': audio_link['href']})
                continue
                
            # Check for image
            img = clue_div.find('img')
            if img:
                src = img.get('src', '')
                alt = img.get('alt', '')
                clues.append({'type': 'image', 'url': src, 'alt': alt})
                continue
                
            # Check for hidden clue (card with front/back)
            card = clue_div.find('div', class_='card')
            if card:
                back = card.find('div', class_='back')
                if back:
                    text = self.clean_text(back)
                    if text:
                        clues.append(text)
                continue
                
            # Regular text clue
            text = self.clean_text(clue_div)
            # Skip empty or placeholder text
            if text and text not in ['Clue 2', 'Clue 3', 'Clue 4', '?']:
                clues.append(text)
                
        return clues
        
    def extract_answer(self, container) -> str:
        """Extract the answer from a round container."""
        answer_div = container.find('div', class_='answer')
        if answer_div:
            # Look for the back of a card
            back = answer_div.find('div', class_='back')
            if back:
                return self.clean_text(back)
            return self.clean_text(answer_div)
        return ""
        
    def parse_connection_round(self, soup, round_num: int) -> list[dict]:
        """Parse a connection round (Round 1 or 2)."""
        questions = []
        
        # Find the round header
        round_id = f'round{round_num}'
        round_header = soup.find('h2', id=round_id) or soup.find('h2', string=re.compile(f'Round {round_num}'))
        
        if not round_header:
            return questions
            
        # Get all h3 headers (question labels) until next round
        current = round_header.find_next_sibling()
        
        while current:
            # Stop at next round
            if current.name == 'h2' and 'Round' in current.get_text():
                break
                
            if current.name == 'h3':
                label_text = current.get_text(strip=True)
                
                # Find the grid container following this h3
                grid = current.find_next_sibling('div', class_='round')
                if not grid:
                    grid = current.find_next_sibling('div', class_='grid-container')
                    
                if grid:
                    clues = self.extract_clues(grid)
                    answer = self.extract_answer(grid)
                    
                    # Determine the index label
                    index_label = None
                    for i, (greek, symbol) in enumerate(zip(GREEK_LETTERS, GREEK_SYMBOLS)):
                        if greek in label_text or symbol in label_text:
                            index_label = greek
                            break
                    for glyph in EGYPTIAN_GLYPHS:
                        if glyph.lower() in label_text.lower():
                            index_label = glyph
                            break
                            
                    questions.append({
                        'label': index_label or label_text,
                        'clues': clues,
                        'answer': answer
                    })
                    
            current = current.find_next_sibling()
            
        return questions
        
    def parse_wall_round(self, soup) -> list[dict]:
        """Parse Round 3 (Connecting Wall)."""
        walls = []
        
        round_header = soup.find('h2', id='round3') or soup.find('h2', string=re.compile('Round 3'))
        
        if not round_header:
            return walls
            
        current = round_header.find_next_sibling()
        
        while current:
            if current.name == 'h2' and 'Round' in current.get_text():
                break
                
            if current.name == 'h3':
                label_text = current.get_text(strip=True)
                
                # Find the question div containing wall-container
                question_div = current.find_next_sibling('div', class_='question')
                
                if question_div:
                    groups = []
                    wall_container = question_div.find('div', class_='wall-container')
                    
                    if wall_container:
                        # Parse the 4 groups (group1, group2, group3, group4)
                        for group_num in range(1, 5):
                            group_class = f'group{group_num}'
                            items = []
                            connection = ""
                            
                            # Find all clue cells for this group
                            for clue_cell in wall_container.find_all('div', class_=re.compile(f'{group_class}-clue')):
                                clue_div = clue_cell.find('div', class_='clue')
                                if clue_div:
                                    text = self.clean_text(clue_div)
                                    if text:
                                        items.append(text)
                                        
                            # Find the answer for this group
                            answer_label = wall_container.find('label', class_=f'{group_class}-answer')
                            if answer_label:
                                back = answer_label.find('div', class_='back')
                                if back:
                                    connection = self.clean_text(back)
                                    
                            if items or connection:
                                groups.append({
                                    'items': items,
                                    'connection': connection
                                })
                    else:
                        # Fallback: try to extract raw text
                        text = self.clean_text(question_div)
                        if text:
                            groups = self.parse_wall_raw_text(text)
                            
                    walls.append({
                        'label': label_text,
                        'groups': groups
                    })
                    
            current = current.find_next_sibling()
            
        return walls
        
    def parse_wall_raw_text(self, text: str) -> list[dict]:
        """Parse raw wall text into groups (fallback for older format)."""
        groups = []
        
        # Split on "Answer" markers which typically follow the connection
        parts = re.split(r'\s+Answer\s*', text)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            words = part.split()
            
            if len(words) >= 5:
                # Heuristic: first 4 items, rest is connection
                items = words[:4]
                connection = ' '.join(words[4:])
                
                groups.append({
                    'items': items,
                    'connection': connection
                })
            elif words:
                groups.append({'raw_text': part})
                
        return groups
        
    def parse_vowels_round(self, soup) -> list[dict]:
        """Parse Round 4 (Missing Vowels)."""
        categories = []
        
        round_header = soup.find('h2', id='round4') or soup.find('h2', string=re.compile('Round 4'))
        
        if not round_header:
            return categories
            
        # Find the vowel round container
        vowel_div = soup.find('div', class_='vowel-round')
        
        if vowel_div:
            current_category = ""
            current_clues = []
            
            for child in vowel_div.children:
                if not hasattr(child, 'name') or child.name is None:
                    continue
                    
                # Category header
                if 'category' in child.get('class', []):
                    # Save previous category if exists
                    if current_category or current_clues:
                        categories.append({
                            'category': current_category,
                            'clues': current_clues
                        })
                    current_category = self.clean_text(child)
                    current_clues = []
                    
                # Missing vowels clue/answer
                elif 'missing-vowels' in child.get('class', []):
                    card = child.find('div', class_='card')
                    if card:
                        front = card.find('div', class_='front')  # The puzzle (consonants only)
                        back = card.find('div', class_='back')    # The answer
                        
                        clue = self.clean_text(front) if front else ""
                        answer = self.clean_text(back) if back else ""
                        
                        if clue or answer:
                            current_clues.append({
                                'clue': clue,
                                'answer': answer
                            })
                            
            # Save last category
            if current_category or current_clues:
                categories.append({
                    'category': current_category,
                    'clues': current_clues
                })
        else:
            # Fallback: try to parse raw text
            content_after_header = round_header.find_next_sibling()
            if content_after_header:
                text = self.clean_text(content_after_header)
                if text:
                    categories = self.parse_vowels_raw_text(text)
                    
        return categories
        
    def parse_vowels_raw_text(self, text: str) -> list[dict]:
        """Parse raw missing vowels text into categories and clues."""
        categories = []
        
        # Missing vowels format is typically:
        # "Category Name" followed by pairs of "CLN S" "CLEANS" (consonants then answer)
        # The consonant-only version uses spaces between letter groups
        
        # Pattern: Words with vowels are likely category names or answers
        # Words without vowels (all consonants + spaces) are clues
        
        # Split into potential sections - categories usually start with vowel-containing words
        words = text.split()
        
        current_category = ""
        current_clues = []
        i = 0
        
        while i < len(words):
            word = words[i]
            
            # Check if word contains vowels (likely category or answer)
            has_vowels = bool(re.search(r'[aeiouAEIOU]', word))
            
            # Look for all-caps consonant patterns (clues)
            is_consonant_clue = bool(re.match(r'^[B-DF-HJ-NP-TV-Zb-df-hj-np-tv-z\s]+$', word))
            
            if has_vowels and not is_consonant_clue:
                # This might be a category name or an answer
                # Categories are usually longer phrases at the start of a section
                
                # Collect consecutive words with vowels
                phrase_words = [word]
                j = i + 1
                while j < len(words):
                    next_word = words[j]
                    if re.search(r'[aeiouAEIOU]', next_word):
                        phrase_words.append(next_word)
                        j += 1
                    else:
                        break
                        
                phrase = ' '.join(phrase_words)
                
                # Heuristic: if phrase is long and followed by consonant-only words,
                # it's likely a category
                if j < len(words) and not re.search(r'[aeiouAEIOU]', words[j]):
                    # Save previous category if exists
                    if current_category or current_clues:
                        categories.append({
                            'category': current_category,
                            'clues': current_clues
                        })
                    current_category = phrase
                    current_clues = []
                else:
                    # It's an answer to the previous clue
                    if current_clues and isinstance(current_clues[-1], dict):
                        current_clues[-1]['answer'] = phrase
                    else:
                        current_clues.append({'answer': phrase})
                        
                i = j
            else:
                # Consonant-only clue
                # Collect consecutive consonant-only words
                clue_words = [word]
                j = i + 1
                while j < len(words):
                    next_word = words[j]
                    if not re.search(r'[aeiouAEIOU]', next_word) and re.match(r'^[B-DF-HJ-NP-TV-Zb-df-hj-np-tv-z\s]+$', next_word):
                        clue_words.append(next_word)
                        j += 1
                    else:
                        break
                        
                clue = ' '.join(clue_words)
                current_clues.append({'clue': clue, 'answer': ''})
                i = j
                
        # Save last category
        if current_category or current_clues:
            categories.append({
                'category': current_category,
                'clues': current_clues
            })
            
        return categories if categories else [{'raw_text': text}]
        
    def parse_episode(self, url: str, metadata: dict) -> dict | None:
        """Parse a complete episode page."""
        soup = self.fetch_page(url)
        
        if not soup:
            return None
            
        episode = {
            'url': url,
            'series': metadata['series'],
            'episode_number': metadata['episode_number'],
            'title': metadata['title'],
            'scraped_at': datetime.now().isoformat()
        }
        
        # Try to get title from page if not in metadata
        h1 = soup.find('h1')
        if h1 and not episode['title']:
            episode['title'] = self.clean_text(h1)
            
        # Extract series/episode info from h2 meta
        meta_h2 = soup.find('h2', class_='episode_meta')
        if meta_h2:
            meta_text = self.clean_text(meta_h2)
            series_match = re.search(r'Series\s*(\d+)', meta_text)
            ep_match = re.search(r'Episode\s*(\d+)', meta_text)
            
            if series_match:
                try:
                    episode['series_number'] = int(series_match.group(1))
                except ValueError:
                    pass
            if ep_match and not episode['episode_number']:
                try:
                    episode['episode_number'] = int(ep_match.group(1))
                except ValueError:
                    pass
                    
        # Parse each round
        episode['round1'] = self.parse_connection_round(soup, 1)
        episode['round2'] = self.parse_connection_round(soup, 2)
        episode['round3'] = self.parse_wall_round(soup)
        episode['round4'] = self.parse_vowels_round(soup)
        
        return episode
        
    def run(self, max_episodes: int | None = None, resume: bool = True):
        """Run the scraper."""
        if resume:
            self.load_progress()
            
        # Get episode list
        episode_list = self.get_episode_urls()
        
        if not episode_list:
            print("No episodes found!")
            return
            
        # Filter out already completed episodes
        if resume:
            completed_urls = set(self.progress['completed'])
            to_scrape = [ep for ep in episode_list if ep['url'] not in completed_urls]
            print(f"{len(to_scrape)} episodes remaining to scrape")
        else:
            to_scrape = episode_list
            
        if max_episodes:
            to_scrape = to_scrape[:max_episodes]
            
        # Scrape each episode
        for i, ep_info in enumerate(to_scrape):
            print(f"[{i+1}/{len(to_scrape)}] Scraping: {ep_info['title']}")
            
            try:
                episode = self.parse_episode(ep_info['url'], ep_info)
                
                if episode:
                    self.episodes.append(episode)
                    self.progress['completed'].append(ep_info['url'])
                    r4_clues = sum(len(c.get('clues', [])) for c in episode['round4'])
                    print(f"  ✓ Extracted: R1={len(episode['round1'])}, R2={len(episode['round2'])}, "
                          f"R3={len(episode['round3'])} walls, R4={r4_clues} clues")
                else:
                    self.progress['failed'].append(ep_info['url'])
                    print(f"  ✗ Failed to parse")
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.progress['failed'].append(ep_info['url'])
                
            # Save progress periodically
            if (i + 1) % 10 == 0:
                self.save_progress()
                print(f"  Progress saved ({len(self.episodes)} episodes)")
                
        # Final save
        self.save_progress()
        print(f"\nComplete! Saved {len(self.episodes)} episodes to {OUTPUT_FILE}")
        
        if self.progress['failed']:
            print(f"Failed episodes ({len(self.progress['failed'])}):")
            for url in self.progress['failed']:
                print(f"  - {url}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Only Connect Database')
    parser.add_argument('--max', type=int, help='Maximum episodes to scrape')
    parser.add_argument('--no-resume', action='store_true', help='Start fresh, ignore progress')
    parser.add_argument('--test', action='store_true', help='Test mode: scrape just 3 episodes')
    
    args = parser.parse_args()
    
    # Check for required libraries
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"Missing required library: {e}")
        print("Install with: pip install requests beautifulsoup4")
        return
        
    scraper = OCDBScraper()
    
    max_eps = args.max
    if args.test:
        max_eps = 3
        print("Test mode: scraping 3 episodes")
        
    scraper.run(max_episodes=max_eps, resume=not args.no_resume)


if __name__ == '__main__':
    main()
