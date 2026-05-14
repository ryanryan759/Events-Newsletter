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

# ── Scraping ─────────────────────────────────────────────────
def scrape_text(url: str, max_chars: int = 4000) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ", strip=True).split())
        return text[:max_chars]
    except Exception as e:
        return f"[Could not fetch {url}: {e}]"

def scrape_all(sources: list[str]) -> str:
    chunks = []
    for url in sources:
        text = scrape_text(url)
        chunks.append(f"SOURCE: {url}\n{text}\n")
    return "\n---\n".join(chunks)

# ── Claude curation ──────────────────────────────────────────
def curate_events(raw_text: str, category: str, extra_instructions: str = "") -> list[dict]:
    today = datetime.now()
    one_month = (today + timedelta(days=30)).strftime("%d %B %Y")
    three_months = (today + timedelta(days=90)).strftime("%d %B %Y")

    prompt = f"""You are curating a personal weekly events newsletter for someone based in London.
Today's date: {today.strftime("%d %B %Y")}

CATEGORY: {category}

THEIR PREFERENCES:
- Favourite music artists: {", ".join(FAVOURITE_ARTISTS)}
- Favourite genres: {", ".join(FAVOURITE_GENRES)}
- Curation notes: {CURATION_NOTES}
{extra_instructions}

RAW SCRAPED DATA FROM EVENT WEBSITES:
{raw_text}

Extract and return a JSON array of events. Each event object must have:
- "title": event name
- "date": date string
- "venue": venue name and area of London
- "description": 2 sharp editorial sentences (not touristy, not corporate)
- "price": ticket price or "Free"
- "url": link to event page
- "bucket": either "upcoming_month" (within {one_month}) or "further_ahead" (up to {three_months})
- "category": one of: music | sustainability | art | networking

Return ONLY valid JSON. No markdown, no explanation. 
For upcoming_month: aim for 8-10 events total across categories.
For further_ahead: aim for 2-3 events.
If data is sparse, return what you can find."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def get_music_headlines() -> list[dict]:
    prompt = f"""You are a music journalist writing for a London culture newsletter.
Today: {datetime.now().strftime("%d %B %Y")}

Using your knowledge of live music, return a JSON array of 5-7 notable upcoming live music events 
or festivals happening in the UK (primarily London but can include major UK festivals) over the 
next 12 months that would appeal to someone who loves:

Artists: {", ".join(FAVOURITE_ARTISTS)}
Genres: {", ".join(FAVOURITE_GENRES)}

Include 4-5 events matching their taste and 1-2 genuine surprises — artists outside their usual 
genres but that a culturally curious person might love. Mark surprises with "surprise": true.

Each object must have:
- "title": artist or festival name  
- "date": approximate date or month/year
- "venue": venue or festival site
- "description": one punchy sentence on why this matters
- "url": ticketing or info URL (use real known URLs where possible)
- "price": approximate price range
- "surprise": true or false

Return ONLY valid JSON. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def get_surprise_pick() -> dict:
    prompt = f"""Recommend ONE music artist or event as a total wildcard surprise for someone who loves:
Artists: {", ".join(FAVOURITE_ARTISTS)}
Genres: {", ".join(FAVOURITE_GENRES)}

This should be completely outside their normal taste — could be classical, experimental, folk, 
jazz, spoken word, world music — anything. But it should be something that, on reflection, 
they might genuinely connect with given their broader sensibility.

Return a single JSON object with:
- "artist": name
- "genre": genre
- "why": 2 sentences on why this is worth their attention
- "url": a relevant link (YouTube, Spotify, website)

Return ONLY valid JSON."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"artist": "Erykah Badu", "genre": "Neo-soul", "why": "A curated surprise.", "url": "https://open.spotify.com"}

# ── HTML template ────────────────────────────────────────────
def build_html(events: list[dict], headlines: list[dict], surprise: dict) -> str:
    today_str = datetime.now().strftime("%A %d %B %Y").upper()
    issue_num = datetime.now().strftime("%Y%W")

    upcoming = [e for e in events if e.get("bucket") == "upcoming_month"]
    further  = [e for e in events if e.get("bucket") == "further_ahead"]

    cat_icons = {"music": "◈", "sustainability": "◉", "art": "◆", "networking": "◇"}
    cat_labels = {"music": "MUSIC", "sustainability": "SUSTAINABILITY", "art": "ART & AUCTIONS", "networking": "NETWORKING"}

    def event_card(e: dict) -> str:
        icon  = cat_icons.get(e.get("category", ""), "◈")
        label = cat_labels.get(e.get("category", ""), e.get("category", "").upper())
        price = e.get("price", "")
        price_pill = f'<span style="background:#1a1a1a;color:#c8f542;font-family:\'Courier New\',monospace;font-size:10px;font-weight:700;letter-spacing:1px;padding:3px 8px;border:1px solid #c8f542;">{price.upper()}</span>' if price else ""
        return f"""
<div style="border-top:1px solid #2a2a2a;padding:22px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="color:#666;font-family:'Courier New',monospace;font-size:10px;letter-spacing:2px;">{icon} {label}</span>
    {price_pill}
  </div>
  <h3 style="margin:0 0 4px;font-family:'Georgia',serif;font-size:20px;color:#f0f0f0;font-weight:700;line-height:1.2;">{e.get("title","")}</h3>
  <p style="margin:0 0 8px;font-family:'Courier New',monospace;font-size:11px;color:#888;letter-spacing:1px;">{e.get("date","").upper()} &nbsp;·&nbsp; {e.get("venue","").upper()}</p>
  <p style="margin:0 0 12px;font-family:'Georgia',serif;font-size:14px;color:#aaa;line-height:1.6;">{e.get("description","")}</p>
  <a href="{e.get("url","#")}" style="font-family:'Courier New',monospace;font-size:10px;color:#c8f542;text-decoration:none;letter-spacing:2px;border-bottom:1px solid #c8f542;padding-bottom:1px;">GET TICKETS / INFO →</a>
</div>"""

    def headline_card(h: dict) -> str:
        badge = '<span style="background:#c8f542;color:#000;font-family:\'Courier New\',monospace;font-size:9px;font-weight:700;letter-spacing:1px;padding:2px 6px;margin-left:8px;">SURPRISE</span>' if h.get("surprise") else ""
        return f"""
<div style="border-top:1px solid #2a2a2a;padding:18px 0;display:flex;justify-content:space-between;align-items:flex-start;">
  <div style="flex:1;">
    <div style="display:flex;align-items:center;margin-bottom:4px;">
      <span style="font-family:'Georgia',serif;font-size:16px;color:#f0f0f0;font-weight:700;">{h.get("title","")}</span>
      {badge}
    </div>
    <p style="margin:0 0 4px;font-family:'Courier New',monospace;font-size:10px;color:#666;letter-spacing:1px;">{h.get("date","").upper()} &nbsp;·&nbsp; {h.get("venue","").upper()}</p>
    <p style="margin:0;font-family:'Georgia',serif;font-size:13px;color:#888;line-height:1.5;">{h.get("description","")}</p>
  </div>
  <div style="margin-left:20px;text-align:right;flex-shrink:0;">
    <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:10px;color:#c8f542;">{h.get("price","")}</p>
    <a href="{h.get("url","#")}" style="font-family:'Courier New',monospace;font-size:9px;color:#666;text-decoration:none;letter-spacing:1px;border-bottom:1px solid #444;padding-bottom:1px;">INFO →</a>
  </div>
</div>"""

    upcoming_html = "".join(event_card(e) for e in upcoming) or "<p style='color:#555;font-family:Georgia,serif;padding:20px 0;'>No events found this week — check back next Friday.</p>"
    further_html  = "".join(event_card(e) for e in further)  or "<p style='color:#555;font-family:Georgia,serif;padding:20px 0;'>Nothing notable on the horizon yet.</p>"
    headlines_html = "".join(headline_card(h) for h in headlines) or "<p style='color:#555;font-family:Georgia,serif;padding:20px 0;'>Check back for upcoming shows.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{NEWSLETTER_NAME} — {today_str}</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Georgia,serif;">
<div style="max-width:640px;margin:0 auto;background:#0a0a0a;">

  <!-- MASTHEAD -->
  <div style="padding:48px 40px 32px;border-bottom:3px solid #c8f542;">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;">
      <div>
        <p style="margin:0 0 4px;font-family:'Courier New',monospace;font-size:9px;color:#666;letter-spacing:3px;">ISSUE {issue_num}</p>
        <h1 style="margin:0;font-family:'Georgia',serif;font-size:48px;font-weight:700;color:#f0f0f0;letter-spacing:-1px;line-height:1;">THE<br>DISPATCH</h1>
      </div>
      <div style="text-align:right;">
        <p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#666;letter-spacing:2px;line-height:1.8;">{today_str}<br>LONDON EDITION</p>
      </div>
    </div>
    <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap;">
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#444;letter-spacing:2px;">◈ MUSIC</span>
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#444;letter-spacing:2px;">◉ SUSTAINABILITY</span>
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#444;letter-spacing:2px;">◆ ART &amp; AUCTIONS</span>
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#444;letter-spacing:2px;">◇ NETWORKING</span>
    </div>
  </div>

  <!-- INTRO -->
  <div style="padding:28px 40px;border-bottom:1px solid #1e1e1e;background:#0f0f0f;">
    <p style="margin:0;font-family:'Courier New',monospace;font-size:11px;color:#555;letter-spacing:1px;line-height:1.8;">
      YOUR WEEKLY LONDON CULTURE BRIEF &nbsp;·&nbsp; CURATED EVERY FRIDAY &nbsp;·&nbsp; {len(upcoming)} EVENTS THIS MONTH
    </p>
  </div>

  <!-- THIS MONTH -->
  <div style="padding:40px 40px 0;">
    <div style="margin-bottom:8px;">
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#c8f542;letter-spacing:3px;">THIS MONTH</span>
    </div>
    <h2 style="margin:0 0 4px;font-family:'Georgia',serif;font-size:32px;color:#f0f0f0;font-weight:700;">Upcoming Events</h2>
    <p style="margin:0 0 24px;font-family:'Courier New',monospace;font-size:11px;color:#555;">NEXT 30 DAYS — LONDON</p>
    {upcoming_html}
  </div>

  <!-- FURTHER AHEAD -->
  <div style="padding:40px 40px 0;margin-top:8px;background:#0d0d0d;">
    <div style="margin-bottom:8px;">
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#888;letter-spacing:3px;">ON THE HORIZON</span>
    </div>
    <h2 style="margin:0 0 4px;font-family:'Georgia',serif;font-size:28px;color:#d0d0d0;font-weight:700;">Further Ahead</h2>
    <p style="margin:0 0 24px;font-family:'Courier New',monospace;font-size:11px;color:#555;">1–3 MONTHS OUT</p>
    {further_html}
  </div>

  <!-- MUSIC HEADLINES -->
  <div style="padding:40px 40px 0;margin-top:8px;">
    <div style="margin-bottom:8px;">
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#c8f542;letter-spacing:3px;">MUSIC</span>
    </div>
    <h2 style="margin:0 0 4px;font-family:'Georgia',serif;font-size:32px;color:#f0f0f0;font-weight:700;">Headline Acts &amp; Festivals</h2>
    <p style="margin:0 0 24px;font-family:'Courier New',monospace;font-size:11px;color:#555;">NEXT 12 MONTHS — UK &amp; BEYOND</p>
    {headlines_html}
  </div>

  <!-- SURPRISE PICK -->
  <div style="margin:40px 40px;border:1px solid #c8f542;padding:28px;">
    <p style="margin:0 0 4px;font-family:'Courier New',monospace;font-size:9px;color:#c8f542;letter-spacing:3px;">THIS WEEK'S WILDCARD</p>
    <h3 style="margin:0 0 4px;font-family:'Georgia',serif;font-size:24px;color:#f0f0f0;font-weight:700;">{surprise.get("artist","")}</h3>
    <p style="margin:0 0 12px;font-family:'Courier New',monospace;font-size:10px;color:#666;letter-spacing:1px;">{surprise.get("genre","").upper()}</p>
    <p style="margin:0 0 16px;font-family:'Georgia',serif;font-size:14px;color:#aaa;line-height:1.6;">{surprise.get("why","")}</p>
    <a href="{surprise.get("url","#")}" style="font-family:'Courier New',monospace;font-size:10px;color:#c8f542;text-decoration:none;letter-spacing:2px;border-bottom:1px solid #c8f542;padding-bottom:1px;">LISTEN NOW →</a>
  </div>

  <!-- FOOTER -->
  <div style="padding:28px 40px 40px;border-top:1px solid #1a1a1a;">
    <p style="margin:0 0 8px;font-family:'Courier New',monospace;font-size:9px;color:#333;letter-spacing:2px;">THE DISPATCH &nbsp;·&nbsp; LONDON &nbsp;·&nbsp; EVERY FRIDAY 8AM</p>
    <p style="margin:0;font-family:'Courier New',monospace;font-size:9px;color:#2a2a2a;letter-spacing:1px;">To adjust preferences or sources, edit config.py in your GitHub repository.</p>
  </div>

</div>
</body>
</html>"""

# ── Email sending ────────────────────────────────────────────
def send_email(html: str):
    today_str = datetime.now().strftime("%d %B %Y")
    payload = {
        "from": "The Dispatch <delivered@resend.dev>",
"to": ["ryan.ryan759@gmail.com"],
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
        print(f"✅ Newsletter sent to {TO_EMAIL}")
    else:
        print(f"❌ Resend error {r.status_code}: {r.text}")
        raise RuntimeError("Email sending failed")

# ── Main ─────────────────────────────────────────────────────
def main():
    print("🔍 Scraping music sources...")
    music_raw = scrape_all(MUSIC_SOURCES)

    print("🔍 Scraping sustainability sources...")
    sustain_raw = scrape_all(SUSTAINABILITY_SOURCES)

    print("🔍 Scraping art sources...")
    art_raw = scrape_all(ART_SOURCES)

    print("🤖 Curating events with Claude...")
    music_events  = curate_events(music_raw,   "live music events in London")
    sustain_events = curate_events(sustain_raw, "sustainability talks and networking events in London", "Only include FREE events.")
    art_events    = curate_events(art_raw,     "art exhibitions, private views, and auctions in London")

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
