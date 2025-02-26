#From 2024.01-2025.02
import requests
from bs4 import BeautifulSoup
import re
import csv
import time

# List of monthly archive pages to scrape.
urls = []

# Create an HTTP session with a custom User-Agent.
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/110.0.5481.77 Safari/537.36"
    )
})

def extract_laas_from_post(html):
    """
    Given the full HTML of a single post page,
    return the number of LAAs for each stream if found.
    Specifically looks for:
        Skilled Worker in Manitoba
        Number of Letters of Advice to Apply issued: NNN

        International Education Stream
        Number of Letters of Advice to Apply issued: NNN

        Skilled Worker Overseas
        Number of Letters of Advice to Apply issued: NNN
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try to locate the main content area. Adjust as needed.
    content_div = soup.find("div", class_="entry-content")
    if content_div:
        content_text = content_div.get_text("\n", strip=True)
    else:
        # Fallback: parse the entire HTML if not found
        content_text = soup.get_text("\n", strip=True)

    # Regex pattern example:
    #   Skilled Worker in Manitoba
    #   Number of Letters of Advice to Apply issued: **
    #
    # Explanation:
    #   - We look for the exact stream name (case-insensitive).
    #   - We allow for optional whitespace and newlines.
    #   - We then look for the phrase "Number of Letters of Advice to Apply issued" (case-insensitive).
    #   - We then capture the number (\d+).
    pattern_swm = re.compile(
        r"Skilled Worker in Manitoba\s*.*?Number of Letters of Advice to Apply issued\s*[:\-]?\s*(\d+)",
        re.IGNORECASE | re.DOTALL
    )
    pattern_ies = re.compile(
        r"(International Education Stream|International Students Stream)\s*.*?Number of Letters of Advice to Apply issued\s*[:\-]?\s*(\d+)",
        re.IGNORECASE | re.DOTALL
    )
    pattern_swo = re.compile(
        r"Skilled Worker Overseas\s*.*?Number of Letters of Advice to Apply issued\s*[:\-]?\s*(\d+)",
        re.IGNORECASE | re.DOTALL
    )

    swm_laa = ""
    ies_laa = ""
    swo_laa = ""

    # Search for Skilled Worker in Manitoba
    match_swm = pattern_swm.search(content_text)
    if match_swm:
        swm_laa = match_swm.group(1)

    # Search for International Education Stream
    match_ies = pattern_ies.search(content_text)
    if match_ies:
        ies_laa = match_ies.group(2)

    # Search for Skilled Worker Overseas
    match_swo = pattern_swo.search(content_text)
    if match_swo:
        swo_laa = match_swo.group(1)

    return {
        "Skilled Worker in Manitoba": swm_laa,
        "International Education Stream": ies_laa,
        "Skilled Worker Overseas": swo_laa
    }

draw_data = []

for archive_url in urls:
    print(f"Processing archive page: {archive_url}")
    try:
        archive_resp = session.get(archive_url, timeout=10)
    except requests.RequestException as e:
        print(f"Request failed for {archive_url}: {e}")
        continue

    if archive_resp.status_code != 200:
        print(f"Archive page not fetched (status {archive_resp.status_code}): {archive_url}")
        continue

    archive_soup = BeautifulSoup(archive_resp.text, "html.parser")

    # Find each post on the archive page. 
    # WordPress often uses <article class="post"> or <article id="post-..."> for each blog post.
    articles = archive_soup.find_all("article")
    if not articles:
        print(f"No articles found on {archive_url}")
        continue

    for article in articles:
        # Usually, the post link is in <h2 class="entry-title"> <a href="...">
        title_element = article.find("h2", class_="entry-title")
        if not title_element:
            # Some themes might use <h3> or a different class
            continue

        link_tag = title_element.find("a")
        if not link_tag or not link_tag.has_attr("href"):
            continue

        post_url = link_tag["href"]
        post_title = link_tag.get_text(strip=True)

        # Try to get the date from a <time> element
        time_tag = article.find("time")
        if time_tag and time_tag.has_attr("datetime"):
            post_date = time_tag["datetime"].split("T")[0]
        else:
            post_date = post_title  # fallback if no time tag

        # Fetch the individual post page to parse LAAs
        print(f"  -> Fetching post: {post_url}")
        try:
            post_resp = session.get(post_url, timeout=10)
        except requests.RequestException as e:
            print(f"Request failed for {post_url}: {e}")
            continue

        if post_resp.status_code != 200:
            print(f"Post not fetched (status {post_resp.status_code}): {post_url}")
            continue

        laa_dict = extract_laas_from_post(post_resp.text)

        draw_data.append({
            "Date": post_date,
            "Title": post_title,
            "Skilled Worker in Manitoba": laa_dict["Skilled Worker in Manitoba"],
            "International Education Stream": laa_dict["International Education Stream"],
            "Skilled Worker Overseas": laa_dict["Skilled Worker Overseas"],
            "URL": post_url
        })

        # Small delay to avoid overwhelming the server
        time.sleep(1)

# Sort the results by Date descending if it's in YYYY-MM-DD format.
def parse_date(date_str):
    # Quick attempt to parse a YYYY-MM-DD date. If it fails, return something minimal.
    # This ensures that items with a valid date sort properly, 
    # and items without a valid date end up at the bottom.
    try:
        parts = date_str.split("-")
        if len(parts) == 3:
            y, m, d = parts
            return (int(y), int(m), int(d))
    except:
        pass
    return (0, 0, 0)  # fallback for unknown format

draw_data.sort(key=lambda row: parse_date(row["Date"]), reverse=True)

# Write to CSV
csv_filename = "manitoba_draws.csv"
with open(csv_filename, "w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "Date",
        "Title",
        "Skilled Worker in Manitoba",
        "International Education Stream",
        "Skilled Worker Overseas",
        "URL"
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in draw_data:
        writer.writerow(row)

print(f"\nDone. Extracted {len(draw_data)} draws. CSV saved as {csv_filename}.")
