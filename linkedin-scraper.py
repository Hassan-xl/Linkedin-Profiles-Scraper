from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import random
import urllib.parse
from datetime import datetime
import pandas as pd
import os
import json
import re
from typing import Dict, List

# =========================
# CONFIG
# =========================

SEARCH_QUERY = (
    '("Indexed Universal Life" OR IUL OR LIRP '
    'OR "Life Insurance Retirement Plan" '
    'OR "Cash Value Life Insurance")'
)

KEYWORDS_TO_MATCH = [
    "Indexed Universal Life",
    "IUL",
    "LIRP",
    "Life Insurance Retirement Plan",
    "Cash Value Life Insurance",
]

MAX_PROFILES = 100
SESSION_DIR = "session"
OUTPUT_FILE = "results_100_upgraded.csv"
INTERMEDIATE_URLS = "profile_urls.json"
INTERMEDIATE_ROWS = "rows_partial.json"

HEADLESS = False
SLOW_MO = 50

# Random delay ranges (seconds)
DELAY_BETWEEN_PROFILE_LIST_PAGES = (3, 6)
DELAY_BEFORE_VISIT = (4, 7)
DELAY_AFTER_VISIT = (15, 25)

# =========================
# UTILITIES
# =========================

def safe_inner_text(locator, default=""):
    try:
        return locator.inner_text().strip()
    except Exception:
        return default

def text_from_locator_texts(page, selectors: List[str]) -> str:
    parts = []
    for s in selectors:
        try:
            loc = page.locator(s)
            if loc.count():
                parts.append(loc.all_inner_texts())
        except Exception:
            pass
    # flatten and join
    flat = []
    for p in parts:
        if isinstance(p, list):
            flat.extend(p)
        else:
            flat.append(str(p))
    return "\n".join([x.strip() for x in flat if x and x.strip()])

def match_keywords(text: str, keywords: List[str]) -> List[str]:
    matches = set()
    if not text:
        return []
    lowered = text.lower()
    for kw in keywords:
        # for exact phrase keywords use lower() contains
        if " " in kw:
            if kw.lower() in lowered:
                matches.add(kw)
        else:
            # single tokens (IUL, LIRP) - word boundary match to avoid partials
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, lowered):
                matches.add(kw)
    return sorted(matches)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# =========================
# SCRAPER FUNCTIONS
# =========================

def collect_profile_urls(page, max_profiles: int) -> List[str]:
    """Paginate LinkedIn people search and collect profile URLs until max_profiles or no more found.
       Respects intermediate save to resume."""
    seen_profiles = set()
    # try to resume
    existing = load_json(INTERMEDIATE_URLS)
    if existing:
        seen_profiles.update(existing)
        print(f"Resumed {len(existing)} profile URLs from {INTERMEDIATE_URLS}")

    encode_q = urllib.parse.quote(SEARCH_QUERY)
    page_num = 1
    while len(seen_profiles) < max_profiles:
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={encode_q}&page={page_num}"
        print(f"[search] loading page {page_num} -> {search_url}")
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            print("timeout loading search page, retrying...")
            time.sleep(5)
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                break

        time.sleep(random.uniform(4, 6))
        # ensure People tab
        try:
            people_btn = page.locator("button:has-text('People')").first
            if people_btn and people_btn.count():
                people_btn.click()
                time.sleep(1.5)
        except Exception:
            pass

        # collect in-page profile links
        try:
            profile_urls = page.eval_on_selector_all(
                "a[href^='https://www.linkedin.com/in/'], a[href^='/in/']",
                "els => els.map(e => e.href ? e.href.split('?')[0] : (e.getAttribute('href') || '').split('?')[0])"
            )
            # normalize urls: absolute and filter
            for url in profile_urls:
                if not url:
                    continue
                # handle relative /in/ links that may not include domain
                if url.startswith("/in/"):
                    url = "https://www.linkedin.com" + url
                if "/in/" in url:
                    seen_profiles.add(url.split("?")[0])
                if len(seen_profiles) >= max_profiles:
                    break
        except Exception as e:
            print("Error collecting profile URLs:", e)

        print(f"[search] collected {len(seen_profiles)}/{max_profiles}")
        save_json(INTERMEDIATE_URLS, list(seen_profiles))

        # next page
        page_num += 1
        time.sleep(random.uniform(*DELAY_BETWEEN_PROFILE_LIST_PAGES))
        # safety: break if no new entries for couple pages? Not implemented for brevity

    return list(seen_profiles)[:max_profiles]

def extract_contact_info(page) -> Dict[str, str]:
    """Click Contact info overlay and try to scrape emails, phones, websites and social links."""
    result = {
        "contact_linkedin": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_website": "",
        "contact_other": ""
    }
    try:
        contact_locator = page.locator("a[href*='overlay/contact-info'], a[aria-label*='Contact info'], button[aria-label*='Contact info']")
        if contact_locator.count():
            # try click; sometimes it's an <a> with href to overlay, sometimes a button
            try:
                contact_locator.first.click()
            except Exception:
                # try JS click
                page.evaluate("(el) => el.click()", contact_locator.first)
            # wait for modal/dialog
            dialog = page.locator("div[role='dialog'], div.artdeco-modal__content, section.pv-contact-info")
            try:
                dialog.wait_for(state="visible", timeout=8000)
            except PlaywrightTimeoutError:
                # maybe still opened; continue
                pass
            time.sleep(1.0)

            # collect all link texts and hrefs inside modal
            try:
                # pick up links and list items inside the dialog
                a_elems = dialog.locator("a")
                links = []
                for i in range(a_elems.count()):
                    try:
                        href = a_elems.nth(i).get_attribute("href") or ""
                        text = a_elems.nth(i).inner_text().strip() or ""
                        links.append((text, href))
                    except Exception:
                        continue

                # Also collect any plain list items (li) which may contain phone/email text without anchors
                li_texts = []
                li_elems = dialog.locator("li")
                for i in range(li_elems.count()):
                    try:
                        t = li_elems.nth(i).inner_text().strip()
                        if t:
                            li_texts.append(t)
                    except Exception:
                        continue

                # heuristics: detect email, phone, website
                emails = []
                phones = []
                websites = []
                other = []

                for text, href in links:
                    href_l = (href or "").lower()
                    text_l = (text or "").lower()
                    # email links
                    if href_l.startswith("mailto:") or re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text):
                        if href_l.startswith("mailto:"):
                            emails.append(href.split("mailto:")[-1].split("?")[0])
                        else:
                            m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
                            if m:
                                emails.append(m.group(0))
                    # phone links
                    elif href_l.startswith("tel:") or re.search(r"\+?\d[\d\-\s\(\)]{7,}\d", text):
                        if href_l.startswith("tel:"):
                            phones.append(href.split("tel:")[-1])
                        else:
                            m = re.search(r"\+?\d[\d\-\s\(\)]{7,}\d", text)
                            if m:
                                phones.append(m.group(0))
                    # website links (not linkedin)
                    elif "http" in href_l or href_l.startswith("www"):
                        if "linkedin.com" not in href_l:
                            websites.append(href or text)
                        else:
                            # could be linkedin profile link inside modal
                            result["contact_linkedin"] = href or text
                    else:
                        # fallback
                        if text and not text.startswith("Message"):
                            other.append(f"{text} ({href})" if href else text)

                # also scan li_texts for email/phone
                for t in li_texts:
                    tl = t.lower()
                    em = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", t)
                    ph = re.search(r"\+?\d[\d\-\s\(\)]{7,}\d", t)
                    if em:
                        emails.append(em.group(0))
                    elif ph:
                        phones.append(ph.group(0))
                    else:
                        other.append(t)

                # dedupe
                emails = sorted(set([e.strip() for e in emails if e]))
                phones = sorted(set([re.sub(r'\s+', ' ', p).strip() for p in phones if p]))
                websites = sorted(set([w.strip() for w in websites if w]))

                if emails:
                    result["contact_email"] = ";".join(emails)
                if phones:
                    result["contact_phone"] = ";".join(phones)
                if websites:
                    result["contact_website"] = ";".join(websites)
                if other:
                    result["contact_other"] = ";".join(other)

            except Exception as e:
                print("error parsing contact modal:", e)

            # close the dialog (click close or Esc)
            try:
                close_btn = page.locator("button[aria-label='Dismiss'], button[data-control-name='overlay.close'], button[aria-label='Close']")
                if close_btn.count():
                    close_btn.first.click()
                else:
                    page.keyboard.press("Escape")
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass

            time.sleep(0.6)
    except Exception as e:
        # contact info may not exist for that profile
        # print("contact click error:", e)
        pass

    return result

def extract_profile_data(page, url: str) -> Dict[str, str]:
    """Visit a profile URL and return a dict with scraped fields."""
    row = {
        "profile_url": url,
        "name": "",
        "headline": "",
        "location": "",
        "about": "",
        "experience": "",
        "education": "",
        "skills": "",
        "current_title": "",
        "current_company": "",
        "matched_keywords": "",
        "contact_linkedin": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_website": "",
        "contact_other": "",
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except PlaywrightTimeoutError:
        print(f"[profile] timeout loading {url}")
        return row
    except Exception as e:
        print(f"[profile] error loading {url}: {e}")
        return row

    time.sleep(random.uniform(*DELAY_BEFORE_VISIT))

    # basic header fields
    try:
        # name is often in h1
        name = safe_inner_text(page.locator("h1").first, "")
        row["name"] = name
    except Exception:
        pass

    try:
        # headline often in div.text-body-medium or div.text-body-large
        headline = ""
        if page.locator("div.text-body-medium, div.text-body-large, .pv-text-details__left-panel").count():
            headline = page.locator("div.text-body-medium, div.text-body-large, .pv-text-details__left-panel").first.inner_text().strip()
        else:
            # fallback to first h2 or span
            headline = safe_inner_text(page.locator("div.text-body-medium.break-words").first, "")
        row["headline"] = headline
    except Exception:
        pass

    try:
        # location text
        loc = safe_inner_text(page.locator("span.text-body-small.inline.t-black--light.break-words"), "")
        if not loc:
            # alternate
            loc = safe_inner_text(page.locator(".pv-top-card--list-bullet").first, "")
        row["location"] = loc
    except Exception:
        pass

    # About / Summary
    try:
        about = ""
        # LinkedIn may use section:has-text('About') then inside a div
        if page.locator("section:has-text('About')").count():
            about_loc = page.locator("section:has-text('About')").first
            about = about_loc.locator("div").all_inner_texts()
            about = "\n".join(about).strip()
        else:
            # fallback to top-card summary area
            about = safe_inner_text(page.locator("div.text-body-medium.break-words").first, "")
        row["about"] = about
    except Exception:
        pass

    # Experience
    try:
        # Try to get entire experience section text
        exp = ""
        if page.locator("section:has-text('Experience')").count():
            exp = page.locator("section:has-text('Experience')").first.inner_text().strip()
        else:
            # get blocks with experience item selectors
            exp = text_from_locator_texts(page, [
                "div.pv-profile-section__section-info.section-info",
                "ul.pv-profile-section__section-info li"
            ])
        row["experience"] = exp
    except Exception:
        pass

    # Education
    try:
        edu = ""
        if page.locator("section:has-text('Education')").count():
            edu = page.locator("section:has-text('Education')").first.inner_text().strip()
        row["education"] = edu
    except Exception:
        pass

    # Skills (top skills)
    try:
        skills_text = ""
        # skills container classname may change; try a few
        skills_loc = page.locator("section:has-text('Skills') ul, .pv-skill-categories-section__top-skills, .pv-skill-categories-section")
        if skills_loc.count():
            skills_text = "\n".join(skills_loc.all_inner_texts())
        row["skills"] = skills_text
    except Exception:
        pass

    # Current title/company: try pick first experience item or top-card text
    try:
        # top-card role/company often in ul.pv-top-card--list
        toplist = page.locator("ul.pv-top-card--list, ul.pv-top-card--list-bullet")
        if toplist.count():
            li_texts = toplist.first.all_inner_texts()
            if li_texts:
                # often li_texts[0] is headline/title, li_texts[1] is location etc
                row["current_title"] = li_texts[0] if len(li_texts) > 0 else ""
                # try to locate company from experience first item
        # fallback: parse experience first item
        if page.locator("section:has-text('Experience') li").count():
            first_exp = page.locator("section:has-text('Experience') li").first.inner_text()
            # heuristics: first line is title/company
            row["current_title"] = row["current_title"] or first_exp.split("\n")[0]
            # try company token extraction
            lines = first_exp.split("\n")
            if len(lines) > 1:
                row["current_company"] = lines[1]
    except Exception:
        pass

    # Contact info (overlay)
    try:
        contact = extract_contact_info(page)
        row.update(contact)
    except Exception:
        pass

    # Aggregate searchable text and match keywords
    aggregate_text = " ".join([
        row.get("name", ""),
        row.get("headline", ""),
        row.get("about", ""),
        row.get("experience", ""),
        row.get("education", ""),
        row.get("skills", "")
    ])
    matches = match_keywords(aggregate_text, KEYWORDS_TO_MATCH)
    row["matched_keywords"] = ";".join(matches)

    row["timestamp"] = datetime.utcnow().isoformat()
    return row

# =========================
# MAIN
# =========================

def main():
    os.makedirs(SESSION_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser_type = p.chromium
        context = browser_type.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=HEADLESS,
            slow_mo=SLOW_MO
        )

        page = context.new_page()

        # require manual login
        print("Please log in to LinkedIn in the opened browser window.")
        page.goto("https://www.linkedin.com/login")
        input("👉 After logging in and landing on your feed, press ENTER here to continue...")

        try:
            page.wait_for_url("**/feed**", timeout=120000)
        except PlaywrightTimeoutError:
            print("Timed out waiting for feed URL, but continuing anyway...")

        # 1) collect profile urls
        profile_list = collect_profile_urls(page, MAX_PROFILES)
        print(f"[main] total profiles to visit: {len(profile_list)}")

        # save immediate
        save_json(INTERMEDIATE_URLS, profile_list)

        # try resume existing partial rows
        rows = load_json(INTERMEDIATE_ROWS) or []
        visited = {r.get("profile_url") for r in rows if r.get("profile_url")}

        for i, url in enumerate(profile_list, start=1):
            if url in visited:
                print(f"[{i}/{len(profile_list)}] already scraped {url}, skipping (resume)")
                continue

            print(f"[{i}/{len(profile_list)}] Visiting {url}")
            try:
                row = extract_profile_data(page, url)
                rows.append(row)
                # save partial after each profile to allow resume
                save_json(INTERMEDIATE_ROWS, rows)
            except Exception as e:
                print(f"Error scraping {url}: {e}")

            # polite delay
            time.sleep(random.uniform(*DELAY_AFTER_VISIT))

        # close context
        context.close()

    # save CSV
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    # also save final JSON
    save_json("results_full.json", rows)
    print(f"\nSaved {len(df)} profiles to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()