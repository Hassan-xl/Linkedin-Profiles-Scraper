# 🔍 LinkedIn Profiles Scraper

A Python automation tool that searches **LinkedIn's People search** for professionals matching specific **financial industry keywords**, visits each profile, and exports the data into a structured **CSV and JSON file** — all using a real browser to avoid detection.

---

## ✨ Features

- 🧠 **Keyword-targeted search** — finds professionals mentioning IUL, LIRP, Cash Value Life Insurance, and related terms
- 🌐 **Paginated URL collection** — crawls LinkedIn People search results and collects up to 100 profile URLs
- 👤 **Deep profile extraction** — scrapes name, headline, location, about, experience, education, skills, current title, and company
- 📬 **Contact info extraction** — opens the contact info overlay to capture emails, phone numbers, and websites
- 🔎 **Smart keyword matching** — uses word-boundary regex to ensure accurate matches (no false partial hits)
- 💾 **Resume capability** — saves progress after every profile so no data is lost if the run is interrupted
- 🕐 **Human-like behavior** — random delays (3–25 seconds) between requests to avoid LinkedIn bot detection
- 📁 **Dual output** — exports final results as both `.csv` and `.json`

---

## 🎯 Target Keywords

The scraper searches for profiles containing any of:

- `Indexed Universal Life`
- `IUL`
- `LIRP`
- `Life Insurance Retirement Plan`
- `Cash Value Life Insurance`

These are fully configurable in the `CONFIG` section at the top of the script.

---

## 🛠️ Requirements

```bash
pip install playwright pandas
playwright install chromium
```

---

## ⚙️ Configuration

Edit the `CONFIG` section at the top of `linkedin_scraper.py`:

```python
MAX_PROFILES = 100          # How many profiles to scrape
OUTPUT_FILE = "results.csv" # Output filename
HEADLESS = False            # Set True to run browser in background
```

You can also customize `SEARCH_QUERY` and `KEYWORDS_TO_MATCH` to target any industry or niche.

---

## ▶️ Usage

```bash
python linkedin_scraper.py
```

1. A Chromium browser window will open
2. **Manually log in** to your LinkedIn account
3. Press **Enter** in the terminal once you're on your feed
4. The scraper will automatically collect profile URLs, then visit and extract each one

---

## 📁 Output

Results are saved to `results.csv` and `results_full.json` with the following fields:

| Field | Description |
|---|---|
| `name` | Full name |
| `headline` | Profile headline |
| `location` | Location |
| `about` | About/summary section |
| `experience` | Full experience section text |
| `education` | Education section text |
| `skills` | Top skills |
| `current_title` | Current job title |
| `current_company` | Current company |
| `matched_keywords` | Which target keywords were found |
| `contact_email` | Email (if publicly listed) |
| `contact_phone` | Phone (if publicly listed) |
| `contact_website` | Website (if publicly listed) |
| `profile_url` | Direct LinkedIn profile link |
| `timestamp` | Time of scrape |

---

## 🔄 Resume Support

If the script crashes or is interrupted, simply run it again — it will automatically skip already-scraped profiles using the intermediate save files:

- `profile_urls.json` — collected profile URLs
- `rows_partial.json` — partially scraped rows

---

## 📝 Notes

- LinkedIn's free accounts have profile view limits — use a **Sales Navigator** or **Recruiter** account for larger scrapes
- The scraper uses a **persistent browser session** stored in the `session/` folder — you only need to log in once
- Manual login is intentional to avoid storing credentials in code

---

## ⚠️ Disclaimer

This tool is intended for **personal or research use only**. Ensure your usage complies with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement). The authors are not responsible for any misuse or account restrictions.

---

## 📄 License

MIT License
