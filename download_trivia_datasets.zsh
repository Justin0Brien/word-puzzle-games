#!/usr/bin/env zsh
set -euo pipefail

# Base directory to store everything (can be overridden by first argument)
BASE_DIR="${1:-trivia_datasets}"

echo "Using base directory: $BASE_DIR"
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

# Helper: download a file using curl or wget
download_file() {
  local url="$1"
  local out="$2"

  if [ -f "$out" ]; then
    echo "  -> $out already exists, skipping download."
    return 0
  fi

  echo "  -> Downloading $url -> $out"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --show-error --output "$out" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$out" "$url"
  else
    echo "ERROR: Neither curl nor wget is available; cannot download $url" >&2
    return 1
  fi
}

# Helper: clone or update a git repo
clone_repo() {
  local repo_url="$1"
  local target_dir="$2"

  if [ -d "$target_dir/.git" ]; then
    echo "  -> Updating existing repo in $target_dir"
    git -C "$target_dir" pull --ff-only || {
      echo "  -> git pull failed in $target_dir, leaving as is."
    }
  else
    echo "  -> Cloning $repo_url into $target_dir"
    git clone "$repo_url" "$target_dir"
  fi
}

echo "==============================="
echo "1. GitHub datasets"
echo "==============================="

echo "1.1 OpenTriviaQA (uberspot/OpenTriviaQA)"
clone_repo "https://github.com/uberspot/OpenTriviaQA.git" "OpenTriviaQA"

echo "1.2 Open-trivia-database (el-cms/Open-trivia-database)"
clone_repo "https://github.com/el-cms/Open-trivia-database.git" "Open-trivia-database"

echo
echo "==============================="
echo "2. TriviaQA (University of Washington)"
echo "==============================="

mkdir -p "TriviaQA"
cd "TriviaQA"

# RC version (reading comprehension, includes supporting docs)
TRIVIAQA_RC_URL="https://nlp.cs.washington.edu/triviaqa/data/triviaqa-rc.tar.gz"
TRIVIAQA_RC_ARCHIVE="triviaqa-rc.tar.gz"

# Unfiltered QA version (110k Q–A pairs, better for IR / general QA)
TRIVIAQA_UNF_URL="https://nlp.cs.washington.edu/triviaqa/data/triviaqa-unfiltered.tar.gz"
TRIVIAQA_UNF_ARCHIVE="triviaqa-unfiltered.tar.gz"

echo "2.1 Downloading TriviaQA RC dataset"
download_file "$TRIVIAQA_RC_URL" "$TRIVIAQA_RC_ARCHIVE" || echo "  -> Failed to download TriviaQA RC archive."

echo "2.2 Downloading TriviaQA unfiltered dataset"
download_file "$TRIVIAQA_UNF_URL" "$TRIVIAQA_UNF_ARCHIVE" || echo "  -> Failed to download TriviaQA unfiltered archive."

echo "2.3 Extracting any downloaded TriviaQA archives"
for f in *.tar.gz; do
  [ -f "$f" ] || continue
  dir="${f%.tar.gz}"
  if [ -d "$dir" ]; then
    echo "  -> Directory $dir already exists, skipping extraction of $f"
    continue
  fi
  echo "  -> Extracting $f into $dir"
  mkdir -p "$dir"
  tar -xzf "$f" -C "$dir"
done

cd ..

echo
echo "==============================="
echo "3. Optional: Kaggle mirrors (OpenTDB and OpenTriviaQA pack)"
echo "==============================="

if command -v kaggle >/dev/null 2>&1; then
  echo "kaggle CLI found, attempting Kaggle downloads."

  # 3.1 OpenTDB questions (all categories) – mirror of Open Trivia Database
  echo "3.1 Open Trivia Database (OpenTDB) from Kaggle"
  mkdir -p "OpenTDB_kaggle"
  kaggle datasets download \
    -d shreyasur965/open-trivia-database-quiz-questions-all-categories \
    -p OpenTDB_kaggle \
    --unzip || echo "  -> Failed to download or unzip OpenTDB Kaggle dataset."

  # 3.2 OpenTriviaQA packaged as a Kaggle dataset (redundant but convenient)
  echo "3.2 OpenTriviaQA packaged dataset from Kaggle"
  mkdir -p "OpenTriviaQA_kaggle"
  kaggle datasets download \
    -d mexwell/opentriviaqa-database \
    -p OpenTriviaQA_kaggle \
    --unzip || echo "  -> Failed to download or unzip OpenTriviaQA Kaggle dataset."

else
  echo "kaggle CLI not found."
  echo "If you want the Kaggle mirrors (OpenTDB etc.), install and configure the Kaggle CLI, then re-run:"
  echo "  pip install kaggle"
  echo "and set up your API token (~/.kaggle/kaggle.json)."
fi

echo
echo "All download steps completed (or attempted)."
echo "Datasets are under: $(pwd)"
