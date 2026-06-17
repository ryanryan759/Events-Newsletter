import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import anthropic
from config import *

# ── API clients ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
RESEND_API_KEY    = os.environ["RESEND_API_KEY"]
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0)"}

# ── Sources ──────────────────────────────────────────────────

TICKETING_SOURCES = [
    "https://dice.fm/browse/london",
    "https://www.skiddle.com/whats-on/London/",
    "https://www.shoobs.com/london",
    "https://www.ticketmaster.co.uk/discover/concerts/london",
    "https://www.residentadvisor.net/events/uk/london",
]

NAMED_VENUE_SOURCES = [
    "https://www.shacklewellarms.com/events",
    "https://jagolondon.com/events",
    "https://www.thehaggerston.com/events",
    "https://nighttales.co.uk/events",
    "https://bambi.london/events",
    "https://www.dalstonsuperstore.com/events",
    "https://www.vortexjazz.co.uk/events",
    "https://phonox.co.uk/events",
    "https://peckhampalais.co.uk/events",
    "https://www.electricbrixton.com/events",
    "https://www.thecause.co.uk/events",
    "https://www.hootenanny.co.uk/events",
    "https://www.union-chapel.org.uk/whats-on",
    "https://www.o2academyislington.co.uk/events",
    "https://maboroshi.co.uk/events",
]

DICE_GENRE_SOURCES = [
    "https://dice.fm/browse/london/afrobeats",
    "https://dice.fm/browse/london/grime",
    "https://dice.fm/browse/london/house",
    "https://dice.fm/browse/london/dancehall",
    "https://dice.fm/browse/london/techno",
    "https://dice.fm/browse/london/uk-rap",
]

SONGKICK_SOURCES = [
    "https://www.songkick.com/artists/potter-payper/calendar",
    "https://www.songkick.com/artists/skrapz/calendar",
    "https://www.songkick.com/artists/benny-the-butcher/calendar",
    "https://www.songkick.com/artists/conway-the-machine/calendar",
    "https://www.songkick.com/artists/jamie-xx/calendar",
    "https://www.songkick.com/artists/fred-again/calendar",
    "https://www.songkick.com/artists/mavado/calendar",
    "https://www.songkick.com/artists/parker-mccollum/calendar",
    "https://www.songkick.com/artists/burna-boy/calendar",
    "https://www.songkick.com/artists/j-hus/calendar",
    "https://www.songkick.com/artists/pa-salieu/calendar",
]

ART_SOURCES = [
    "https://www.newexhibitions.com/calendar",
    "https://whitechapelgallery.org/exhibitions/",
    "https://www.serpentinegalleries.org/whats-on/",
    "https://www.victoria-miro.com/exhibitions/",
    "https://www.southlondon-gallery.org/whats-on/",
    "https://www.tate.org.uk/whats-on",
    "https://www.saatchigallery.com/whats-on",
    "https://www.christies.com/en/london",
    "https://www.sothebys.com/en/london",
]

SUSTAINABILITY_SOURCES = [
    "https://www.eventbrite.co.uk/d/united-kingdom--london/sustainability/",
    "https://www.iema.net/events",
    "https://www.edie.net/events/",
    "https://www.green-alliance.org.uk/events/",
    "https://www.forumforthefuture.org/events",
    "https://www.lsx.org.uk/events/",
    "https://www.meetup.com/find/?keywords=sustainability&location=London",
]

# ── Scraping ─────────────────────────────────────────────────
def scrape_text(url: str, max_chars: int = 3500) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if text and len(text) > 3 and any(k in href.lower() for k in [
                "event", "gig", "show", "ticket", "night", "live", "exhibit", "concert", "tour"
            ]):
                full = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                links.append(f"LINK: {text} -> {full}")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ", strip=True).split())
        link_block = "\n".join(links[:40])
        return f"{text[:max_chars]}\n\nEVENT LINKS FOUND:\n{link_block}"
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"

def scrape_all(sources: list) -> str:
    chunks = []
    for url in sources:
        text = scrape_text(url)
        chunks.append(f"SOURCE: {url}\n{text}\n")
    return "\n---\n".join(chunks)

# ── Claude curation ───────────────────────────────────────────
def curate_music_events(raw_text: str) -> list:
    today = datetime.now()
    one_month    = (today + timedelta(days=30)).strftime("%d %B %Y")
    three_months = (today + timedelta(days=90)).strftime("%d %B %Y")

    prompt = f"""You are curating the MUSIC section of a personal London events newsletter.
Today: {today.strftime("%d %B %Y")}

PRIORITY AREAS: Hackney, Dalston, Walthamstow, Islington. Also Peckham, Brixton, East London.
FAVOURITE ARTISTS: {", ".join(FAVOURITE_ARTISTS)}
FAVOURITE GENRES: {", ".join(FAVOURITE_GENRES)}
CURATION NOTES: {CURATION_NOTES}

INSTRUCTIONS:
- Return 8-10 upcoming_month events and 2-3 further_ahead events
- MIX small intimate venues (Shacklewell Arms, Jago, Haggerston, Night Tales, Bambi, Vortex)
  WITH medium venues (Electric Brixton, Peckham Palais, O2 Islington)
- Use DIRECT event page URLs from the EVENT LINKS FOUND sections where available
- Prioritise genre matches: afrobeats, grime, UK rap, house, dancehall, techno, soca, Latin
- If a favourite artist has a London show in the data, it MUST be included
- Write descriptions in a sharp editorial tone referencing the artist or genre specifically

RAW DATA:
{raw_text}

Return a JSON array. Each object:
- "title": artist or night name
- "date": specific date if found
- "venue": venue name + neighbourhood
- "description": 2 punchy editorial sentences
- "price": price or "Free"
- "url": direct event page URL from the links above, else ticketing homepage
- "bucket": "upcoming_month" (before {one_month}) or "further_ahead" (before {three_months})
- "category": "music"

Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def curate_art_events(raw_text: str) -> list:
    today = datetime.now()
    one_month = (today + timedelta(days=30)).strftime("%d %B %Y")

    prompt = f"""You are curating the ART section of a personal London events newsletter.
Today: {today.strftime("%d %B %Y")}

INSTRUCTIONS:
- PRIORITISE private views and opening nights above all else
- Use newexhibitions.com as the primary source
- For private views, use the private view date as the event date
- Favour smaller independent galleries over blockbuster shows
- Use DIRECT event links from the EVENT LINKS FOUND sections where available

RAW DATA:
{raw_text}

Return a JSON array of 4-5 events. Each object:
- "title": exhibition or event name
- "date": private view date if available, else opening date
- "venue": gallery name + area
- "description": 2 editorial sentences on the work or artist
- "price": "Free" for private views, else price
- "url": direct event link if found, else gallery website
- "bucket": "upcoming_month" (before {one_month}) or "further_ahead"
- "category": "art"

Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def curate_sustainability_events(raw_text: str) -> list:
    today = datetime.now()
    one_month = (today + timedelta(days=30)).strftime("%d %B %Y")

    prompt = f"""You are curating sustainability and networking events for a London newsletter.
Today: {today.strftime("%d %B %Y")}
FREE events only. London-based only.

RAW DATA:
{raw_text}

Return a JSON array of 3-4 events. Each object:
- "title": event name
- "date": date string
- "venue": venue + area
- "description": 2 editorial sentences
- "price": "Free"
- "url": direct event link if found
- "bucket": "upcoming_month" (before {one_month}) or "further_ahead"
- "category": "sustainability" or "networking"

Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def get_real_music_headlines(songkick_raw: str) -> list:
    today = datetime.now()
    prompt = f"""Extract REAL verified upcoming UK live music events from this Songkick data.
Today: {today.strftime("%d %B %Y")}
ARTISTS: {", ".join(FAVOURITE_ARTISTS)}

SCRAPED SONGKICK DATA:
{songkick_raw}

CRITICAL: Only include events explicitly mentioned in the data above.
Do NOT invent events. If fewer than 3 events appear in the data, return only what you found.

Return a JSON array. Each object:
- "title": "Artist Name — Venue" format
- "date": exact date from the data
- "venue": venue name and city
- "description": one sentence on why this matters
- "url": exact Songkick or ticketing URL from the data
- "price": price if mentioned, else "Check site"
- "surprise": false

Return ONLY valid JSON. No markdown. No invented events."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def get_surprise_pick() -> dict:
    prompt = f"""Recommend ONE music artist as a wildcard for someone who loves:
Artists: {", ".join(FAVOURITE_ARTISTS)}
Genres: {", ".join(FAVOURITE_GENRES)}

Go completely outside their normal taste. Be bold and specific.

Return a single JSON object:
- "artist": name
- "genre": genre
- "why": 2 sentences on why this is worth their attention
- "url": Spotify or YouTube link

Return ONLY valid JSON."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"artist": "Erykah Badu", "genre": "Neo-soul", "why": "A curated surprise.", "url": "https://open.spotify.com"}


# ── HTML — Broadsheet, larger text, single column ─────────────
def build_html(music: list, art: list, sustainability: list, headlines: list, surprise: dict) -> str:
    today_str  = datetime.now().strftime("%A %d %B %Y").upper()
    date_short = datetime.now().strftime("%d %B %Y")
    issue_num  = datetime.now().strftime("%Y%W")

    upcoming_music = [e for e in music         if e.get("bucket") == "upcoming_month"]
    upcoming_art   = [e for e in art           if e.get("bucket") == "upcoming_month"]
    upcoming_sust  = [e for e in sustainability if e.get("bucket") == "upcoming_month"]
    further        = [e for e in (music + art + sustainability) if e.get("bucket") == "further_ahead"]

    # Music always first
    upcoming = upcoming_music + upcoming_art + upcoming_sust
    total    = len(upcoming)

    cat_colors = {"music": "#8B3A3A", "sustainability": "#2d6e1a", "art": "#1a3a6e", "networking": "#5a3a6e"}
    cat_icons  = {"music": "◈", "sustainability": "◉", "art": "◆", "networking": "◇"}
    cat_labels = {"music": "MUSIC", "sustainability": "SUSTAINABILITY", "art": "ART & AUCTIONS", "networking": "NETWORKING"}

    def price_badge(price: str) -> str:
        if not price:
            return ""
        is_free = "free" in price.lower()
        bg     = "#e8f5e1" if is_free else "#f9f6f0"
        color  = "#2d6e1a" if is_free else "#555"
        border = "#a3c98a" if is_free else "#ccc"
        return f'<span style="background:{bg};color:{color};border:1px solid {border};font-family:\'Courier New\',monospace;font-size:10px;font-weight:700;letter-spacing:1px;padding:3px 9px;">{price.upper()}</span>'

    def event_card(e: dict) -> str:
        icon  = cat_icons.get(e.get("category",""), "◈")
        label = cat_labels.get(e.get("category",""), e.get("category","").upper())
        color = cat_colors.get(e.get("category",""), "#8B3A3A")
        return f"""
<div style="padding:22px 0;border-top:1px solid #d0ccc0;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-family:'Courier New',monospace;font-size:10px;color:{color};letter-spacing:2px;font-weight:700;">{icon} {label}</td>
    <td align="right">{price_badge(e.get("price",""))}</td>
  </tr></table>
  <h3 style="margin:8px 0 5px;font-family:Georgia,serif;font-size:22px;font-weight:700;color:#1a1a1a;line-height:1.2;">{e.get("title","")}</h3>
  <p style="margin:0 0 8px;font-family:'Courier New',monospace;font-size:11px;color:#777;letter-spacing:1px;">{e.get("date","").upper()} &nbsp;·&nbsp; {e.get("venue","")}</p>
  <p style="margin:0 0 12px;font-family:Georgia,serif;font-size:16px;color:#333;line-height:1.7;font-style:italic;">{e.get("description","")}</p>
  <a href="{e.get("url","#")}" style="font-family:'Courier New',monospace;font-size:10px;color:#1a1a1a;letter-spacing:2px;text-decoration:none;border-bottom:1px solid #1a1a1a;padding-bottom:2px;">MORE INFO →</a>
</div>"""

    def headline_row(h: dict) -> str:
        badge = '<span style="background:#1a1a1a;color:#f9f6f0;font-family:\'Courier New\',monospace;font-size:9px;font-weight:700;letter-spacing:1px;padding:2px 7px;margin-left:8px;">WILDCARD</span>' if h.get("surprise") else ""
        return f"""
<div style="padding:20px 0;border-top:1px solid #d0ccc0;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td valign="top" style="width:65%;">
      <p style="margin:0 0 4px;font-family:Georgia,serif;font-size:18px;font-weight:700;color:#1a1a1a;line-height:1.2;">{h.get("title","")}{badge}</p>
      <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:10px;color:#777;letter-spacing:1px;">{h.get("date","").upper()} &nbsp;·&nbsp; {h.get("venue","")}</p>
      <p style="margin:0;font-family:Georgia,serif;font-size:15px;color:#444;font-style:italic;line-height:1.6;">{h.get("description","")}</p>
    </td>
    <td valign="middle" align="right" style="padding-left:20px;">
      <p style="margin:0 0 8px;font-family:'Courier New',monospace;font-size:11px;color:#1a1a1a;font-weight:700;">{h.get("price","")}</p>
      <a href="{h.get("url","#")}" style="font-family:'Courier New',monospace;font-size:10px;color:#555;text-decoration:none;border-bottom:1px solid #bbb;padding-bottom:1px;letter-spacing:1px;">TICKETS →</a>
    </td>
  </tr></table>
</div>"""

    upcoming_html  = "".join(event_card(e) for e in upcoming)  or "<p style='font-family:Georgia,serif;font-size:16px;color:#999;font-style:italic;padding:20px 0;'>No events found this week.</p>"
    further_html   = "".join(event_card(e) for e in further)   or "<p style='font-family:Georgia,serif;font-size:16px;color:#999;font-style:italic;padding:20px 0;'>Nothing notable on the horizon yet.</p>"
    headlines_html = "".join(headline_row(h) for h in headlines) if headlines else "<p style='font-family:Georgia,serif;font-size:16px;color:#999;font-style:italic;padding:20px 0;'>No verified upcoming shows found this week — check Songkick directly.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Dispatch — {date_short}</title>
</head>
<body style="margin:0;padding:24px 0;background:#ede9e0;font-family:Georgia,serif;">
<div style="max-width:620px;margin:0 auto;background:#f9f6f0;border:1px solid #c8c4b8;">

  <!-- MASTHEAD -->
  <div style="padding:36px 44px 22px;border-bottom:3px double #1a1a1a;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td valign="bottom">
        <p style="margin:0 0 3px;font-family:'Courier New',monospace;font-size:9px;color:#999;letter-spacing:3px;">ISSUE {issue_num} &nbsp;·&nbsp; LONDON EDITION</p>
        <h1 style="margin:0;font-family:Georgia,serif;font-size:56px;font-weight:700;color:#1a1a1a;letter-spacing:-2px;line-height:0.95;">The Dispatch</h1>
      </td>
      <td valign="bottom" align="right" style="padding-bottom:4px;">
        <p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#999;letter-spacing:1px;line-height:2.2;">{today_str}</p>
        <p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#999;letter-spacing:1px;">{total} EVENTS THIS MONTH</p>
      </td>
    </tr></table>
    <p style="margin:12px 0 0;font-family:'Courier New',monospace;font-size:9px;letter-spacing:3px;">
      <span style="color:#8B3A3A;">◈ MUSIC</span> &nbsp;&nbsp;
      <span style="color:#2d6e1a;">◉ SUSTAINABILITY</span> &nbsp;&nbsp;
      <span style="color:#1a3a6e;">◆ ART &amp; AUCTIONS</span> &nbsp;&nbsp;
      <span style="color:#5a3a6e;">◇ NETWORKING</span>
    </p>
  </div>

  <!-- DATELINE -->
  <div style="padding:10px 44px;border-bottom:1px solid #d0ccc0;background:#f0ece2;">
    <p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:2px;">
      YOUR WEEKLY LONDON CULTURE BRIEF &nbsp;·&nbsp; HACKNEY · DALSTON · ISLINGTON · WALTHAMSTOW
    </p>
  </div>

  <!-- THIS MONTH — music first, single column -->
  <div style="padding:32px 44px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><h2 style="margin:0;font-family:Georgia,serif;font-size:12px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">This Month</h2></td>
      <td align="right"><span style="font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:1px;">NEXT 30 DAYS</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:8px;"></div>
    {upcoming_html}
  </div>

  <!-- ON THE HORIZON -->
  <div style="padding:28px 44px 12px;background:#f2ede3;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><h2 style="margin:0;font-family:Georgia,serif;font-size:12px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">On The Horizon</h2></td>
      <td align="right"><span style="font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:1px;">1–3 MONTHS OUT</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:8px;"></div>
    {further_html}
  </div>

  <!-- VERIFIED HEADLINE ACTS -->
  <div style="padding:28px 44px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <h2 style="margin:0;font-family:Georgia,serif;font-size:12px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">Headline Acts &amp; Tours</h2>
        <p style="margin:4px 0 0;font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:1px;">VERIFIED DATES FROM SONGKICK</p>
      </td>
      <td align="right" valign="top"><span style="font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:1px;">NEXT 12 MONTHS</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:8px;"></div>
    {headlines_html}
  </div>

  <!-- WILDCARD -->
  <div style="margin:12px 44px 32px;padding:24px 28px;background:#1a1a1a;">
    <p style="margin:0 0 3px;font-family:'Courier New',monospace;font-size:9px;color:#888;letter-spacing:3px;">THIS WEEK'S WILDCARD</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;"><tr>
      <td valign="top">
        <h3 style="margin:0 0 3px;font-family:Georgia,serif;font-size:24px;font-weight:700;color:#f9f6f0;">{surprise.get("artist","")}</h3>
        <p style="margin:0 0 12px;font-family:'Courier New',monospace;font-size:10px;color:#666;letter-spacing:2px;">{surprise.get("genre","").upper()}</p>
        <p style="margin:0;font-family:Georgia,serif;font-size:15px;color:#aaa;line-height:1.7;font-style:italic;">{surprise.get("why","")}</p>
      </td>
      <td valign="middle" align="right" style="padding-left:20px;white-space:nowrap;">
        <a href="{surprise.get("url","#")}" style="font-family:'Courier New',monospace;font-size:10px;color:#f9f6f0;text-decoration:none;border:1px solid #555;padding:8px 14px;letter-spacing:1px;">LISTEN →</a>
      </td>
    </tr></table>
  </div>

  <!-- FOOTER -->
  <div style="padding:18px 44px 28px;border-top:3px double #1a1a1a;background:#f0ece2;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#aaa;letter-spacing:2px;">THE DISPATCH &nbsp;·&nbsp; LONDON &nbsp;·&nbsp; EVERY FRIDAY 8AM</p></td>
      <td align="right"><p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#ccc;letter-spacing:1px;">Edit config.py to update preferences</p></td>
    </tr></table>
  </div>

</div>
</body>
</html>"""


# ── Email ────────────────────────────────────────────────────
def send_email(html: str):
    today_str = datetime.now().strftime("%d %B %Y")
    payload = {
        "from": "The Dispatch <onboarding@resend.dev>",
        "to": "ryan.ryan759@gmail.com",
        "subject": f"The Dispatch — Your London Week · {today_str}",
        "html": html,
    }
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    if r.status_code in (200, 201):
        print("✅ Newsletter sent to ryan.ryan759@gmail.com")
    else:
        print(f"❌ Resend error {r.status_code}: {r.text}")
        raise RuntimeError("Email sending failed")


# ── Main ────────────────────────────────────────────────────
def main():
    print("🔍 Scraping ticketing platforms...")
    ticketing_raw = scrape_all(TICKETING_SOURCES)

    print("🔍 Scraping named venues...")
    venues_raw = scrape_all(NAMED_VENUE_SOURCES)

    print("🔍 Scraping Dice genre pages...")
    genre_raw = scrape_all(DICE_GENRE_SOURCES)

    music_raw = ticketing_raw + "\n---\n" + venues_raw + "\n---\n" + genre_raw

    print("🔍 Scraping Songkick for verified artist dates...")
    songkick_raw = scrape_all(SONGKICK_SOURCES)

    print("🔍 Scraping art sources...")
    art_raw = scrape_all(ART_SOURCES)

    print("🔍 Scraping sustainability sources...")
    sustain_raw = scrape_all(SUSTAINABILITY_SOURCES)

    print("🤖 Curating music events...")
    music_events = curate_music_events(music_raw)

    print("🤖 Curating art events...")
    art_events = curate_art_events(art_raw)

    print("🤖 Curating sustainability events...")
    sustain_events = curate_sustainability_events(sustain_raw)

    print("🎵 Extracting verified headline acts from Songkick...")
    headlines = get_real_music_headlines(songkick_raw)

    print("🎲 Getting wildcard pick...")
    surprise = get_surprise_pick()

    print("📰 Building newsletter...")
    html = build_html(music_events, art_events, sustain_events, headlines, surprise)

    print("📬 Sending email...")
    send_email(html)

if __name__ == "__main__":
    main()
