import os
import json
import re
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(BASE_DIR, "lyrics.json")
SOURCE_URL = "https://bocsonglyrics.blogspot.com/"


def get_client():
    """Build the Gemini client. Deferred to call-time (not import-time) so
    importing this module doesn't blow up if GEMINI_API_KEY isn't set —
    important since app.py imports this module to power the admin sync button."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a key from https://aistudio.google.com/apikey and export it before running this."
        )
    return genai.Client(api_key=api_key)


def load_local_songbook():
    if not os.path.exists(LOCAL_FILE) or os.stat(LOCAL_FILE).st_size == 0:
        return []
    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_local_songbook(data):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def normalize_lyrics(t):
    t = re.sub(r"[^\w\s]", "", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()[:200]


def fetch_and_integrate(log=print):
    """Scrape SOURCE_URL, ask Gemini to extract song title/lyrics pairs, and
    merge any new ones into lyrics.json (skipping duplicate titles or
    duplicate lyric bodies under a different title).

    `log` is called with progress strings — defaults to print() for CLI use;
    the admin web route passes something that collects the messages instead.

    Returns a dict: {"ok": bool, "added": int, "added_titles": [...],
    "skipped_titles": [...], "error": str or None}
    """
    log(f"Connecting to source: {SOURCE_URL}...")
    try:
        response = requests.get(SOURCE_URL, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log(f"Error accessing website: {e}")
        return {"ok": False, "added": 0, "added_titles": [], "skipped_titles": [], "error": str(e)}

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "nav", "footer"]):
        element.decompose()

    raw_content = soup.get_text(separator="\n")
    snippet = raw_content[:8000]

    log("Sending content to Gemini AI for structured parsing...")

    prompt = (
        "Extract all church song titles and their full respective lyrics from the text below. "
        "Format the output strictly as a valid raw JSON array of objects. Do not wrap the output in markdown code blocks, backticks, or write the word 'json'. "
        "Each object must have exactly these keys:\n"
        "- 'title': The string title of the song\n"
        "- 'text': The full lyrics string, preserving stanza layout using standard newline characters (\\n)\n"
        "- 'favorite': false\n\n"
        f"Webpage Content:\n{snippet}"
    )

    try:
        client = get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        ai_response = response.text.strip()

        if ai_response.startswith("```"):
            ai_response = ai_response.strip("`").replace("json\n", "", 1).strip()

        extracted_songs = json.loads(ai_response)
    except Exception as e:
        log(f"Failed to parse AI output: {e}")
        return {"ok": False, "added": 0, "added_titles": [], "skipped_titles": [], "error": str(e)}

    local_songs = load_local_songbook()
    existing_titles = {song["title"].lower().strip() for song in local_songs}
    existing_bodies = {normalize_lyrics(song.get("text", "")) for song in local_songs}
    existing_bodies.discard("")

    added_titles = []
    skipped_titles = []

    for song in extracted_songs:
        normalized_title = song["title"].lower().strip()
        normalized_body = normalize_lyrics(song.get("text", ""))

        if normalized_title in existing_titles:
            log(f"-> Skipped (Already Exists): {song['title']}")
            skipped_titles.append(song["title"])
            continue
        if normalized_body and normalized_body in existing_bodies:
            log(f"-> Skipped (Same lyrics under another title): {song['title']}")
            skipped_titles.append(song["title"])
            continue

        local_songs.append(song)
        existing_titles.add(normalized_title)
        if normalized_body:
            existing_bodies.add(normalized_body)
        log(f"-> Successfully Integrated: {song['title']}")
        added_titles.append(song["title"])

    if added_titles:
        save_local_songbook(local_songs)
        log(f"\nSuccess! Added {len(added_titles)} new songs to your local songbook.")
    else:
        log("\nNo new unique songs found to add.")

    return {
        "ok": True,
        "added": len(added_titles),
        "added_titles": added_titles,
        "skipped_titles": skipped_titles,
        "error": None,
    }


if __name__ == "__main__":
    fetch_and_integrate()
