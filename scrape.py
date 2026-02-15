#!/usr/bin/env python3
"""
Scrape Chiang Mai running races from Runlah.com and output races.json
"""

import json
import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime


URL = "https://www.runlah.com/en/calendar/location?province=Chiang+Mai"
BASE = "https://www.runlah.com"


class RunlahParser(HTMLParser):
    """Parse the Runlah Chiang Mai calendar page to extract race cards."""

    def __init__(self):
        super().__init__()
        self.races = []
        self.current_race = None
        self.in_h1 = False
        self.capture_text = False
        self.capture_target = None
        self.depth = 0
        self.card_depth = 0
        self.in_card = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        href = attrs_dict.get("href", "")
        src = attrs_dict.get("src", "")
        alt = attrs_dict.get("alt", "")

        # Detect race card links: <a> tags linking to /en/<eventid>
        if tag == "a" and href and re.match(r"^/en/[A-Za-z0-9_]+$", href):
            # Check it's not a team link or navigation link
            if "/teams/" not in href and href not in ["/en", "/en/calendar", "/en/results",
                "/en/promote", "/en/about", "/en/terms", "/en/privacy",
                "/en/user/registers", "/en/user/settings"]:
                # Start a potential race card
                if self.current_race is None:
                    self.current_race = {
                        "name": "",
                        "url": BASE + href,
                        "image": "",
                        "date": "",
                        "dateDisplay": "",
                        "location": ""
                    }

        # Capture banner image inside a card context
        if tag == "img" and self.current_race and not self.current_race["image"]:
            if src and "/images/event/" in src:
                if src.startswith("/"):
                    src = BASE + src
                self.current_race["image"] = src

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self.current_race:
            # Try to capture the race name (first substantial text in the link)
            if not self.current_race["name"] and len(text) > 3:
                # Skip navigation / generic text
                if text not in ["Detail", "Register now!", "View all other events..."]:
                    self.current_race["name"] = text

            # Try to capture date
            if not self.current_race["date"]:
                date_match = re.match(
                    r"^((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})$",
                    text
                )
                if date_match:
                    self.current_race["dateDisplay"] = date_match.group(1)
                    try:
                        dt = datetime.strptime(date_match.group(1), "%B %d, %Y")
                        self.current_race["date"] = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                # Also try "DD-DD Month YYYY" or "DD Month YYYY" patterns
                date_match2 = re.match(r"^(\d{1,2}(?:-\d{1,2})?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})$", text)
                if date_match2 and not self.current_race["date"]:
                    self.current_race["dateDisplay"] = date_match2.group(1)
                    # Parse first date
                    parts = date_match2.group(1).split()
                    day = parts[0].split('-')[0]
                    month_year = " ".join(parts[1:])
                    try:
                        dt = datetime.strptime(f"{day} {month_year}", "%d %B %Y")
                        self.current_race["date"] = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

            # Try to capture location (contains "Chiang Mai province")
            if not self.current_race["location"] and "Chiang Mai" in text and "province" in text.lower():
                self.current_race["location"] = text.replace(" province", "").strip()

    def handle_endtag(self, tag):
        # Finalize a race card when we have enough data
        if self.current_race:
            r = self.current_race
            if r["name"] and r["date"]:
                # Check for duplicates
                urls = [existing["url"] for existing in self.races]
                if r["url"] not in urls:
                    # Clean up location
                    if not r["location"]:
                        r["location"] = "Chiang Mai"
                    self.races.append(r)
                self.current_race = None
            # Give up if we've seen too many tags without finding a date
            # (reset after encountering another <a>)


def scrape():
    """Fetch the page and parse races."""
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ChiangMaiRaces/1.0)"
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    parser = RunlahParser()
    parser.feed(html)

    # Sort by date
    races = sorted(parser.races, key=lambda r: r["date"])

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in races:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    return unique


def main():
    races = scrape()
    print(f"Found {len(races)} races in Chiang Mai")

    with open("races.json", "w", encoding="utf-8") as f:
        json.dump({
            "lastUpdated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "https://www.runlah.com/en/calendar/location?province=Chiang+Mai",
            "races": races
        }, f, ensure_ascii=False, indent=2)

    # Print summary
    for r in races:
        print(f"  {r['date']} — {r['name']}")


if __name__ == "__main__":
    main()
