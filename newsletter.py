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

# ── All venue & event sources ────────────────────────────────

# Primary ticketing sources
TICKETING_SOURCES = [
    "https://dice.fm/browse/london",
    "https://www.skiddle.com/whats-on/London/",
    "https://www.shoobs.com/london",
    "https://www.ticketmaster.co.uk/discover/concerts/london",
]

# Your named venues — direct what's on pages
NAMED_VENUE_SOURCES = [
    "https://www.shacklewellarms.com/events",
    "https://phonox.co.uk/events",
    "https://www.thecause.co.uk/events",
    "https://www.thehaggerston.com/events",
    "https://jagolondon.com/events",
    "https://www.hootenanny.co.uk/events",
    "https://www.electricbrixton.com/events",
    "https://www.thecarpetshop.co.uk/events",
    "https://peckhampalais.co.uk/events",
    "https://nighttales.co.uk/events",
    "https://bambi.london/events",
]

# Timeout 50 best nights out venues extracted
TIMEOUT_VENUE_SOURCES = [
    "https://www.residentadvisor.net/events/uk/london",
    "https://fold.london/events",
    "https://www.fabriclondon.com/events",
    "https://www.ovalspace.co.uk/events",
    "https://www.howlclub.com/events",
    "https://www.moth-club.co.uk/events",
    "https://www.corsica-studios.co.uk/events",
    "https://www.totteridgevalley.co.uk/events",
    "https://www.nts.live/shows",
    "https://www.gigseekr.com/uk/london/all/all",
]

# Art sources — newexhibitions.com as primary
ART_SOURCES = [
    "https://www.newexhibitions.com/calendar",
    "https://www.tate.org.uk/whats-on",
    "https://www.saatchigallery.com/whats-on",
    "https://whitechapelgallery.org/exhibitions/",
    "https://www.serpentinegalleries.org/whats-on/",
    "https://www.victoria-miro.com/exhibitions/",
    "https://www.southlondon-gallery.org/whats-on/",
    "https://www.friezeacademy.com/events",
    "https://www.christies.com/en/london",
    "https://www.sothebys.com/en/london",
    "https://www.bonhams.com/auction/london/",
]

# Sustainability sources
SUSTAINABILITY_SOURCES = [
    "https://www.eventbrite.co.uk/d/united-kingdom--london/sustainability/",
    "https://www.iema.net/events",
    "https://www.edie.net/events/",
    "https://www.green-alliance.org.uk/events/",
    "https://www.forumforthefuture.org/events",
    "https://www.lsx.org.uk/events/",
    "https://www.meetup.com/find/?keywords=sustainability&location=London",
    "https://carbonliteracy.com/events/",
]

# ── Scraping ─────────────────────────────────────────────────
def scrape_text(url: str, max_chars: int = 3500) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")

        # Try to extract event-specific links before stripping
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if text and len(text) > 3 and any(k in href.lower() for k in [
                "event", "gig", "show", "ticket", "night", "live", "exhibit", "auction"
            ]):
                full = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                links.append(f"LINK: {text} -> {full}")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ", strip=True).split())

        link_block = "\n".join(links[:30])
        combined = f"{text[:max_chars]}\n\nEVENT LINKS FOUND:\n{link_block}"
        return combined
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"

def scrape_all(sources: list) -> str:
    chunks = []
    for url in sources:
        text = scrape_text(url)
        chunks.append(f"SOURCE: {url}\n{text}\n")
    return "\n---\n".join(chunks)

# ── Claude curation ──────────────────────────────────────────
def curate_music_events(raw_text: str) -> list:
    today = datetime.now()
    one_month    = (today + timedelta(days=30)).strftime("%d %B %Y")
    three_months = (today + timedelta(days=90)).strftime("%d %B %Y")

    prompt = f"""You are curating a personal weekly music events newsletter for someone based in London.
Today's date: {today.strftime("%d %B %Y")}

THEIR MUSIC PREFERENCES:
- Favourite artists: {", ".join(FAVOURITE_ARTISTS)}
- Favourite genres: {", ".join(FAVOURITE_GENRES)}
- Curation notes: {CURATION_NOTES}

IMPORTANT INSTRUCTIONS:
- Include a MIX of small intimate venue gigs AND larger shows
- Prioritise events at these named venues: Shacklewell Arms, Phonox, The Cause, The Haggerston, 
  Jago, Hootennany, Electric Brixton, Carpet Shop, Peckham Palais, Night Tales, Bambi, Fabric, 
  FOLD, Oval Space, Corsica Studios, Moth Club
- If you find an event link in the scraped data, USE THAT EXACT LINK — do not use the homepage
- Include events matching preferred genres AND artists, weighted toward afrobeats, grime, 
  UK rap, house, dancehall, techno, soca, Latin

RAW SCRAPED DATA:
{raw_text}

Return a JSON array. Each event object must have:
- "title": artist/event name
- "date": date string  
- "venue": venue name and area
- "description": 2 sharp editorial sentences — not generic, mention the artist/genre specifically
- "price": ticket price or "Free"
- "url": DIRECT link to that specific event page if found, otherwise ticketing homepage
- "bucket": "upcoming_month" (within {one_month}) or "further_ahead" (up to {three_months})
- "category": "music"

Aim for 6-8 upcoming_month events and 1-2 further_ahead events.
Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def curate_other_events(raw_text: str, category: str, extra: str = "") -> list:
    today = datetime.now()
    one_month    = (today + timedelta(days=30)).strftime("%d %B %Y")
    three_months = (today + timedelta(days=90)).strftime("%d %B %Y")

    prompt = f"""You are curating a personal weekly events newsletter for someone based in London.
Today's date: {today.strftime("%d %B %Y")}
CATEGORY: {category}
{extra}

CURATION NOTES: {CURATION_NOTES}

RAW SCRAPED DATA:
{raw_text}

Return a JSON array. Each event object must have:
- "title": event name
- "date": date string
- "venue": venue name and area
- "description": 2 sharp editorial sentences
- "price": ticket price or "Free"
- "url": DIRECT link to that specific event page if found in the data, otherwise source homepage
- "bucket": "upcoming_month" (within {one_month}) or "further_ahead" (up to {three_months})
- "category": one of: sustainability | art | networking

Aim for 4-6 upcoming_month events. Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def get_music_headlines() -> list:
    prompt = f"""You are a music journalist writing for a London culture newsletter.
Today: {datetime.now().strftime("%d %B %Y")}

Return a JSON array of 5-7 notable upcoming live music events or festivals in the UK 
over the next 12 months for someone who loves:
Artists: {", ".join(FAVOURITE_ARTISTS)}
Genres: {", ".join(FAVOURITE_GENRES)}

Include 4-5 matching their taste and 1-2 genuine surprises (mark with "surprise": true).
Mix big festival headline acts with notable smaller shows.

Each object must have:
- "title": artist or festival name
- "date": approximate date or month/year
- "venue": venue or festival site
- "description": one punchy sentence on why this matters
- "url": real ticketing or info URL
- "price": approximate price range
- "surprise": true or false

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


def get_surprise_pick() -> dict:
    prompt = f"""Recommend ONE music artist as a total wildcard for someone who loves:
Artists: {", ".join(FAVOURITE_ARTISTS)}
Genres: {", ".join(FAVOURITE_GENRES)}

Completely outside their normal taste — classical, experimental, folk, jazz, spoken word, 
world music — anything bold. Should be something they might genuinely connect with.

Return a single JSON object:
- "artist": name
- "genre": genre
- "why": 2 sentences on why worth their attention
- "url": YouTube, Spotify, or website link

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


# ── HTML template — Broadsheet ────────────────────────────────
def build_html(events: list, headlines: list, surprise: dict) -> str:
    today_str  = datetime.now().strftime("%A %d %B %Y").upper()
    date_short = datetime.now().strftime("%d %B %Y")
    issue_num  = datetime.now().strftime("%Y%W")

    upcoming = [e for e in events if e.get("bucket") == "upcoming_month"]
    further  = [e for e in events if e.get("bucket") == "further_ahead"]

    cat_icons  = {"music": "◈", "sustainability": "◉", "art": "◆", "networking": "◇"}
    cat_labels = {"music": "MUSIC", "sustainability": "SUSTAINABILITY", "art": "ART & AUCTIONS", "networking": "NETWORKING"}

    def price_badge(price: str) -> str:
        if not price:
            return ""
        is_free = "free" in price.lower()
        bg     = "#e8f5e1" if is_free else "#f9f6f0"
        color  = "#2d6e1a" if is_free else "#555"
        border = "#a3c98a" if is_free else "#ccc"
        return f'<span style="background:{bg};color:{color};border:1px solid {border};font-family:\'Courier New\',monospace;font-size:9px;font-weight:700;letter-spacing:1px;padding:2px 7px;">{price.upper()}</span>'

    def event_card(e: dict) -> str:
        icon  = cat_icons.get(e.get("category",""), "◈")
        label = cat_labels.get(e.get("category",""), e.get("category","").upper())
        return f"""
<div style="padding:16px 0;border-top:1px solid #d0ccc0;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-family:'Courier New',monospace;font-size:9px;color:#999;letter-spacing:2px;">{icon} {label}</td>
    <td align="right">{price_badge(e.get("price",""))}</td>
  </tr></table>
  <h3 style="margin:6px 0 3px;font-family:Georgia,serif;font-size:17px;font-weight:700;color:#1a1a1a;line-height:1.25;">{e.get("title","")}</h3>
  <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:9px;color:#888;letter-spacing:1px;">{e.get("date","").upper()} &nbsp;·&nbsp; {e.get("venue","")}</p>
  <p style="margin:0 0 8px;font-family:Georgia,serif;font-size:13px;color:#444;line-height:1.6;font-style:italic;">{e.get("description","")}</p>
  <a href="{e.get("url","#")}" style="font-family:'Courier New',monospace;font-size:9px;color:#1a1a1a;letter-spacing:1px;text-decoration:none;border-bottom:1px solid #1a1a1a;padding-bottom:1px;">MORE INFO →</a>
</div>"""

    def grid_events(event_list: list) -> str:
        rows = []
        for i in range(0, len(event_list), 2):
            left  = event_card(event_list[i])
            right = event_card(event_list[i+1]) if i+1 < len(event_list) else ""
            rows.append(f"""
<table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td width="48%" valign="top" style="padding-right:16px;">{left}</td>
    <td width="4%"></td>
    <td width="48%" valign="top">{right}</td>
  </tr>
</table>""")
        return "".join(rows)

    def headline_row(h: dict) -> str:
        badge = '<span style="background:#1a1a1a;color:#f9f6f0;font-family:\'Courier New\',monospace;font-size:8px;font-weight:700;letter-spacing:1px;padding:2px 6px;margin-left:8px;">WILDCARD</span>' if h.get("surprise") else ""
        return f"""
<tr>
  <td valign="top" style="padding:12px 0;border-top:1px solid #d0ccc0;width:58%;">
    <p style="margin:0 0 2px;font-family:Georgia,serif;font-size:14px;font-weight:700;color:#1a1a1a;">{h.get("title","")}{badge}</p>
    <p style="margin:0 0 4px;font-family:'Courier New',monospace;font-size:9px;color:#888;letter-spacing:1px;">{h.get("date","").upper()} &nbsp;·&nbsp; {h.get("venue","")}</p>
    <p style="margin:0;font-family:Georgia,serif;font-size:12px;color:#555;font-style:italic;line-height:1.5;">{h.get("description","")}</p>
  </td>
  <td valign="top" style="padding:12px 0 12px 20px;border-top:1px solid #d0ccc0;text-align:right;">
    <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:10px;color:#1a1a1a;font-weight:700;">{h.get("price","")}</p>
    <a href="{h.get("url","#")}" style="font-family:'Courier New',monospace;font-size:9px;color:#555;text-decoration:none;border-bottom:1px solid #bbb;padding-bottom:1px;letter-spacing:1px;">INFO →</a>
  </td>
</tr>"""

    upcoming_html  = grid_events(upcoming) if upcoming else "<p style='font-family:Georgia,serif;color:#999;font-style:italic;padding:16px 0;'>No events found this week — check back next Friday.</p>"
    further_html   = grid_events(further)  if further  else "<p style='font-family:Georgia,serif;color:#999;font-style:italic;padding:16px 0;'>Nothing notable on the horizon yet.</p>"
    headlines_html = "".join(headline_row(h) for h in headlines) if headlines else "<tr><td><p style='font-family:Georgia,serif;color:#999;font-style:italic;'>Check back for upcoming shows.</p></td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Dispatch — {date_short}</title>
</head>
<body style="margin:0;padding:24px 0;background:#ede9e0;font-family:Georgia,serif;">
<div style="max-width:660px;margin:0 auto;background:#f9f6f0;border:1px solid #c8c4b8;">

  <!-- MASTHEAD -->
  <div style="padding:32px 40px 20px;border-bottom:3px double #1a1a1a;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td valign="bottom">
          <p style="margin:0 0 2px;font-family:'Courier New',monospace;font-size:8px;color:#999;letter-spacing:3px;">ISSUE {issue_num} &nbsp;·&nbsp; LONDON EDITION</p>
          <h1 style="margin:0;font-family:Georgia,serif;font-size:52px;font-weight:700;color:#1a1a1a;letter-spacing:-2px;line-height:0.95;">The Dispatch</h1>
        </td>
        <td valign="bottom" align="right" style="padding-bottom:4px;">
          <p style="margin:0;font-family:'Courier New',monospace;font-size:8px;color:#999;letter-spacing:1px;line-height:2;">{today_str}</p>
          <p style="margin:0;font-family:'Courier New',monospace;font-size:8px;color:#999;letter-spacing:1px;">{len(upcoming)} EVENTS THIS MONTH</p>
        </td>
      </tr>
    </table>
    <p style="margin:10px 0 0;font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:3px;">
      ◈ MUSIC &nbsp;&nbsp; ◉ SUSTAINABILITY &nbsp;&nbsp; ◆ ART &amp; AUCTIONS &nbsp;&nbsp; ◇ NETWORKING
    </p>
  </div>

  <!-- DATELINE BAR -->
  <div style="padding:8px 40px;border-bottom:1px solid #d0ccc0;background:#f0ece2;">
    <p style="margin:0;font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:2px;">
      YOUR WEEKLY LONDON CULTURE BRIEF &nbsp;·&nbsp; CURATED EVERY FRIDAY 8AM
    </p>
  </div>

  <!-- THIS MONTH -->
  <div style="padding:28px 40px 8px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><h2 style="margin:0;font-family:Georgia,serif;font-size:11px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">This Month</h2></td>
      <td align="right"><span style="font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:1px;">NEXT 30 DAYS</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:6px;"></div>
    {upcoming_html}
  </div>

  <!-- DIVIDER -->
  <div style="margin:0 40px;border-top:1px solid #d0ccc0;"></div>

  <!-- ON THE HORIZON -->
  <div style="padding:24px 40px 8px;background:#f2ede3;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><h2 style="margin:0;font-family:Georgia,serif;font-size:11px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">On The Horizon</h2></td>
      <td align="right"><span style="font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:1px;">1–3 MONTHS OUT</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:6px;"></div>
    {further_html}
  </div>

  <!-- MUSIC HEADLINES -->
  <div style="padding:24px 40px 8px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><h2 style="margin:0;font-family:Georgia,serif;font-size:11px;font-weight:700;color:#1a1a1a;letter-spacing:3px;text-transform:uppercase;">Headline Acts &amp; Festivals</h2></td>
      <td align="right"><span style="font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:1px;">NEXT 12 MONTHS</span></td>
    </tr></table>
    <div style="border-top:3px solid #1a1a1a;margin-top:6px;"></div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {headlines_html}
    </table>
  </div>

  <!-- WILDCARD PICK -->
  <div style="margin:16px 40px 28px;padding:20px 24px;background:#1a1a1a;border:1px solid #333;">
    <p style="margin:0 0 2px;font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:3px;">THIS WEEK'S WILDCARD</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;"><tr>
      <td valign="top">
        <h3 style="margin:0 0 2px;font-family:Georgia,serif;font-size:20px;font-weight:700;color:#f9f6f0;">{surprise.get("artist","")}</h3>
        <p style="margin:0 0 10px;font-family:'Courier New',monospace;font-size:9px;color:#666;letter-spacing:2px;">{surprise.get("genre","").upper()}</p>
        <p style="margin:0;font-family:Georgia,serif;font-size:13px;color:#bbb;line-height:1.6;font-style:italic;">{surprise.get("why","")}</p>
      </td>
      <td valign="middle" align="right" style="padding-left:20px;white-space:nowrap;">
        <a href="{surprise.get("url","#")}" style="font-family:'Courier New',monospace;font-size:9px;color:#f9f6f0;text-decoration:none;border:1px solid #555;padding:6px 12px;letter-spacing:1px;">LISTEN →</a>
      </td>
    </tr></table>
  </div>

  <!-- FOOTER -->
  <div style="padding:16px 40px 24px;border-top:3px double #1a1a1a;background:#f0ece2;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <p style="margin:0;font-family:'Courier New',monospace;font-size:8px;color:#aaa;letter-spacing:2px;">THE DISPATCH &nbsp;·&nbsp; LONDON &nbsp;·&nbsp; EVERY FRIDAY 8AM</p>
      </td>
      <td align="right">
        <p style="margin:0;font-family:'Courier New',monospace;font-size:8px;color:#ccc;letter-spacing:1px;">Edit config.py to update preferences</p>
      </td>
    </tr></table>
  </div>

</div>
</body>
</html>"""


# ── Email sending ────────────────────────────────────────────
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
        print(f"✅ Newsletter sent to ryan.ryan759@gmail.com")
    else:
        print(f"❌ Resend error {r.status_code}: {r.text}")
        raise RuntimeError("Email sending failed")


# ── Main ─────────────────────────────────────────────────────
def main():
    print("🔍 Scraping ticketing platforms...")
    ticketing_raw = scrape_all(TICKETING_SOURCES)

    print("🔍 Scraping named venues...")
    venues_raw = scrape_all(NAMED_VENUE_SOURCES)

    print("🔍 Scraping wider London nightlife venues...")
    timeout_raw = scrape_all(TIMEOUT_VENUE_SOURCES)

    music_raw = ticketing_raw + "\n---\n" + venues_raw + "\n---\n" + timeout_raw

    print("🔍 Scraping sustainability sources...")
    sustain_raw = scrape_all(SUSTAINABILITY_SOURCES)

    print("🔍 Scraping art sources...")
    art_raw = scrape_all(ART_SOURCES)

    print("🤖 Curating music events...")
    music_events = curate_music_events(music_raw)

    print("🤖 Curating sustainability events...")
    sustain_events = curate_other_events(
        sustain_raw,
        "sustainability talks and networking events in London",
        "Only include FREE events."
    )

    print("🤖 Curating art events...")
    art_events = curate_other_events(
        art_raw,
        "art exhibitions and auctions in London",
        """IMPORTANT: 
- Prioritise PRIVATE VIEWS and opening nights above regular exhibition runs
- Use newexhibitions.com as the primary source
- For private views, use the private view date as the event date
- Favour smaller independent galleries over blockbuster shows
- Include auction preview events where possible"""
    )

    all_events = music_events + sustain_events + art_events

    print("🎵 Generating music headlines...")
    headlines = get_music_headlines()

    print("🎲 Getting surprise pick...")
    surprise = get_surprise_pick()

    print("📰 Building newsletter...")
    html = build_html(all_events, headlines, surprise)

    print("📬 Sending email...")
    send_email(html)

if __name__ == "__main__":
    main()
