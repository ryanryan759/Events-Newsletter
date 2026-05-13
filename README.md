# The Dispatch — Personal London Newsletter

Automated weekly newsletter delivered every Friday at 8am covering London music, sustainability talks, art exhibitions, and networking events.

---

## Setup (one-time, ~15 minutes)

### 1. Create the GitHub repository
- Go to github.com → New repository
- Name it `friday-newsletter`
- Set to **Public**
- Click **Create repository**

### 2. Upload these files
Upload all files in this folder to your new repository:
- `newsletter.py`
- `config.py`
- `requirements.txt`
- `.github/workflows/newsletter.yml`

You can drag and drop them into the GitHub file upload interface.

### 3. Add your secrets
In your repository: **Settings → Secrets and Variables → Actions → New repository secret**

Add these three secrets:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `RESEND_API_KEY` | Your Resend API key |

Your email address is already set in `config.py`.

### 4. Test it
- Go to **Actions** tab in your repository
- Click **Send Friday Newsletter**
- Click **Run workflow → Run workflow**
- Watch it run — you should receive the email within ~2 minutes

---

## Customising

### Add or remove event sources
Edit `config.py` — find the `MUSIC_SOURCES`, `SUSTAINABILITY_SOURCES`, or `ART_SOURCES` lists and add/remove URLs.

### Change artist preferences
Edit the `FAVOURITE_ARTISTS` and `FAVOURITE_GENRES` lists in `config.py`.

### Adjust curation style
Edit the `CURATION_NOTES` string in `config.py` — plain English, just describe what you want.

### Change send time
Edit `.github/workflows/newsletter.yml` — the `cron` line controls the schedule. The format is: `minute hour day month weekday`. Current setting `0 7 * * 5` = 7am UTC every Friday (8am London BST).

---

## Costs
- GitHub Actions: **Free** (2,000 minutes/month on free tier; this uses ~5 minutes/week)
- Resend: **Free** (3,000 emails/month)
- Anthropic API: ~**$0.10–0.20 per newsletter** depending on how much content is scraped
