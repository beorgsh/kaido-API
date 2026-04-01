# Kaido.to Anime Scraper API 🐉

An asynchronous, robust FastAPI-based web scraper for [Kaido.to](https://kaido.to) (an AniWatch/Zoro.to clone). This API utilizes Playwright and Playwright-Stealth to bypass bot protections, intercept network requests, and extract raw `m3u8` streaming links, subtitles, and anime metadata directly from the site.

> **⚠️ Disclaimer:** This project is for **educational purposes only**. Scraping streaming websites may violate their Terms of Service. The repository owner is not responsible for any misuse of this software. Do not use this to pirate content.

---

## ✨ Features

- **Detailed Anime Metadata** — Scrapes advanced info such as Studios, Producers, MAL Score, and seamlessly fetches `AniList IDs` via the AniList GraphQL API.
- **Fully Asynchronous** — Built on FastAPI and Async Playwright for fast, non-blocking requests.
- **Bot Bypass** — Uses `playwright-stealth` and specific Chromium launch arguments to avoid detection.
- **Advanced Resolver** — Intercepts network responses to pull raw `.m3u8` streams, Intro/Outro skip times, and English subtitle tracks.
- **Comprehensive Homepage** — Scrapes Trending, Spotlight, Top 10 (Day/Week/Month), and Recently Added sections.

---

## 🚀 Prerequisites

- Python 3.8+
- [Node.js](https://nodejs.org/) *(sometimes required by Playwright for certain OS environments)*

---

## 🛠️ Installation & Setup

**1. Clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

**2. Create a virtual environment (Recommended):**
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Install Playwright Browsers:**

> This is a mandatory step. The API requires the Chromium browser to function.

```bash
playwright install chromium
```

---

## 💻 Usage

Start the API server using Python:

```bash
python main.py
```

The API will start running at: **http://localhost:7860**

### Environment Variables

| Variable   | Description                                                                 | Default |
|------------|-----------------------------------------------------------------------------|---------|
| `HEADLESS` | Set to `false` to see the browser open and navigate (useful for debugging). | `true`  |

**Example:**
```bash
HEADLESS=false python main.py
```

---

## 📖 API Endpoints

### 1. Check Status
- **Endpoint:** `GET /`
- **Description:** Checks if the API is running.

---

### 2. Get Homepage Data
- **Endpoint:** `GET /home`
- **Description:** Retrieves all homepage sections including Spotlight, Trending, Latest Episodes, Recently Added, Top Upcoming, Top 10 (Day/Week/Month), and Genres.

---

### 3. Search Anime
- **Endpoint:** `GET /search?q={query}`
- **Description:** Searches for an anime by name.
- **Example:** `/search?q=naruto`

---

### 4. Get Anime Info *(Highly Detailed + AniList Sync)*
- **Endpoint:** `GET /info/{anime_id}`
- **Description:** Fetches extensive details about a specific anime. Automatically falls back to AniList's GraphQL API to ensure an accurate `anilist_id`, `mal_id`, and `mal_score` are returned.
- **Example:** `/info/naruto-shippuden-355`

<details>
<summary>📄 Response Example</summary>

```json
{
  "id": "naruto-shippuden-355",
  "title": "Naruto: Shippuden",
  "japanese_title": "Naruto: Shippuden",
  "description": "It has been two and a half years since Naruto Uzumaki...",
  "poster": "https://img.flawlessfiles.com/...jpg",
  "mal_score": 8.26,
  "anilist_id": 21,
  "mal_id": 1735,
  "stats": {
    "duration": "24m",
    "type": "TV",
    "episodes": "500",
    "sub": "500",
    "dub": "500",
    "quality": "HD"
  },
  "more_info": {
    "aired": "Feb 15, 2007 to Mar 23, 2017",
    "premiered": "Winter 2007",
    "status": "Finished Airing",
    "synonyms": "Naruto Hurricane Chronicles"
  },
  "genres": ["Action", "Adventure", "Fantasy"],
  "producers": ["TV Tokyo", "Aniplex", "KSS", "Rakuonsha", "TV Tokyo Music", "Shueisha"],
  "studios": ["Studio Pierrot"],
  "seasons": [
    {
      "id": "naruto-235",
      "title": "Naruto",
      "is_current": false,
      "poster": "https://img.flawlessfiles.com/..."
    }
  ]
}
```
</details>

---

### 5. Get Episodes
- **Endpoint:** `GET /episodes/{anime_id}`
- **Description:** Retrieves the full list of available episodes for an anime.
- **Example:** `/episodes/naruto-shippuden-355`

---

### 6. Get Episode Servers
- **Endpoint:** `GET /servers/{anime_id}?ep={episode_id}`
- **Description:** Returns a list of available streaming servers (sub, dub, raw) for a specific episode.
- **Example:** `/servers/naruto-shippuden-355?ep=8840`

---

### 7. Resolve Stream ✨
- **Endpoint:** `GET /resolve/{anime_id}?ep={episode_id}&type={type}&server={server}`
- **Description:** Intercepts the embed player and returns the direct `.m3u8` HLS streaming link, subtitle tracks (English prioritized), and intro/outro timestamps.

**Query Parameters:**

| Parameter | Required | Description                                             | Default  |
|-----------|----------|---------------------------------------------------------|----------|
| `ep`      | ✅ Yes   | The episode ID.                                         | —        |
| `type`    | ❌ No    | `sub` or `dub`                                          | `sub`    |
| `server`  | ❌ No    | `hd-1` (Vidstreaming) or `hd-2` (Vidcloud)             | `hd-1`   |

**Example:** `/resolve/naruto-shippuden-355?ep=8840&type=sub&server=hd-1`

<details>
<summary>📄 Response Example</summary>

```json
{
  "episode": "8840",
  "type": "sub",
  "embed_url": "https://kaido.to/embed/...",
  "available_servers": [],
  "sources": [
    {
      "file": "https://megacloud.tv/stream/....m3u8",
      "type": "hls"
    }
  ],
  "tracks": [
    {
      "file": "https://megacloud.tv/subtitles/eng.vtt",
      "label": "English",
      "kind": "captions",
      "default": true
    }
  ],
  "encrypted": false,
  "intro": { "start": 120, "end": 210 },
  "outro": { "start": 1350, "end": 1440 },
  "server": "hd-1"
}
```
</details>

---

## 📂 Project Structure

Upon running the app, a folder named `browser_data/` will be generated in the root directory. This acts as a persistent browser profile to help maintain cookies and lower the chances of getting rate-limited or blocked by Cloudflare.

> **Remember to add `browser_data/` to your `.gitignore` file.**

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](#).
