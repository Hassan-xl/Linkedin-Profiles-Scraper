# Linkedin-Profiles-Scraper


LinkedIn Profile Scraper — Code Description
This is a Python-based LinkedIn profile scraper built using Playwright for browser automation. Its purpose is to search LinkedIn for professionals matching specific financial industry keywords — such as Indexed Universal Life (IUL), LIRP, and Cash Value Life Insurance — and extract their profile data into a structured CSV file.
How It Works:
The script opens a real Chromium browser window and prompts the user to manually log in to LinkedIn. This avoids storing credentials in code. Once logged in, it runs in two phases:

URL Collection — It paginates through LinkedIn's People search results for the configured query and collects up to 100 profile URLs, saving them intermediately to a JSON file so the run can be resumed if interrupted.
Profile Extraction — For each profile URL, it visits the page and scrapes: name, headline, location, about section, experience, education, skills, current title, current company, and contact information (email, phone, website) from the contact info overlay.

After extracting all text, it runs keyword matching against the target terms using word-boundary regex — ensuring accurate matches rather than partial hits.
Key Features:

Random delays between requests (3–25 seconds) to mimic human behavior and avoid detection
Resume capability — partial results are saved after every profile so no data is lost if the run crashes
Final output exported as both CSV and JSON

Output fields: profile URL, name, headline, location, about, experience, education, skills, current title, current company, matched keywords, contact details, and timestamp.
