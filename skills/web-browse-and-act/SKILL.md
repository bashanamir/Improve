---
name: web-browse-and-act
description: Drive a real browser against any website — load pages, read their actual content, click buttons, fill and submit forms, log in, handle CAPTCHAs by pausing for a human, and verify that an action really took effect instead of assuming a click succeeded. Not tied to any specific site, supplier, or workflow. Use whenever the user wants a script/pipeline/agent to interact with a website end-to-end (search, purchase, form-fill, data entry) rather than just fetch/parse a static page or call an API. Trigger on phrases like "browse this site and do X", "log into X and Y", "add this to my cart on X", "fill out this form", "automate this website".
---

# Web Browse & Act

A generic browser-automation layer for standalone scripts/pipelines/agents.
This is not extracted from existing code — there wasn't any yet — it's
built fresh from Playwright, generalized so it works against any site
rather than one specific supplier or workflow.

## When to use this vs. other tools

- **This skill**: for code the user runs themselves (a local pipeline, an
  unattended agent) that needs to *act* on a live website — click, fill
  forms, log in, add to cart, submit — not just read a page's HTML.
- **Simple content fetching** (just need the text/data from a page, no
  interaction required): a plain HTTP request + HTML parsing is lighter-
  weight than a full browser. Don't reach for this skill for that.
- **Within-conversation browsing** (the user wants something looked up or
  clicked *right now*, in this chat): if a browsing tool/connector is
  already available in the current session, use that directly instead of
  writing a script.

## Core idea

Three primitives cover almost everything:
1. **Read** what's actually on the page before deciding what to do next —
   don't guess at page structure blind.
2. **Act** — click, fill, submit — using selectors discovered from what you
   just read.
3. **Verify** — after an action, check the resulting page state. A click
   "succeeding" (no exception thrown) is not proof anything happened;
   confirm the expected outcome actually shows up.

Plus two things that come up on real sites constantly and are worth
handling generically rather than per-site: **logins** and **CAPTCHAs**.

## Prerequisites

```bash
pip install -r scripts/requirements.txt --break-system-packages
playwright install chromium
```

## How to use it

Everything lives in `scripts/browser_agent.py`, as a `WebAgent` class.
Import and use it in your own script — don't reimplement Playwright
boilerplate inline.

```python
from browser_agent import WebAgent

# headless=False by default and recommended: if a CAPTCHA shows up, a
# human needs to actually see the window to solve it.
agent = WebAgent(headless=False)

agent.goto("https://example.com/login")
agent.login(
    username_selector="#email",
    password_selector="#password",
    submit_selector="button[type=submit]",
    username="me@example.com",
    password="hunter2",
)

# See what's actually on the page before acting
print(agent.read_page())
print(agent.list_interactive_elements())  # rough map of buttons/inputs/links

agent.fill("#search-box", "widget X")
agent.click("text=Search")

agent.click("text=Add to cart")
# Don't just trust the click — confirm it actually landed
assert agent.verify_text_present("Added to cart") or agent.verify_on_url("/cart")

agent.screenshot("checkpoint.png")
agent.close()
```

### API summary

| Method | Purpose |
|---|---|
| `goto(url)` | Navigate; auto-pauses if a CAPTCHA is detected on load |
| `read_page()` | Visible text content of the current page |
| `list_interactive_elements()` | Rough list of buttons/inputs/links with their text/id/name — for finding selectors on an unfamiliar page |
| `click(selector)` | CSS selector or Playwright `text=...` syntax |
| `fill(selector, value)` | Fill a single field |
| `fill_form({selector: value, ...}, submit_selector=None)` | Fill multiple fields, optionally submit |
| `select_option(selector, value)` | For `<select>` dropdowns |
| `login(username_selector, password_selector, submit_selector, username, password)` | Generic single-page login |
| `verify_text_present(text)` | Waits for text to appear — use after any action whose success matters |
| `verify_on_url(substring)` | Waits until the URL contains a substring — e.g. confirming redirect to `/cart` |
| `detect_captcha()` | Returns True/False without pausing, if you want to check manually |
| `screenshot(path)` | Full-page screenshot, useful for debugging or as an audit trail |
| `close()` | Always call this when done |

### Persistent login sessions

Pass `user_data_dir` to keep cookies/sessions between runs instead of
logging in fresh every time:
```python
agent = WebAgent(headless=False, user_data_dir="./browser-profile-mysite")
```

## CAPTCHA handling

`goto()` and `click()` automatically check for common CAPTCHA/bot-check
markers (reCAPTCHA, hCaptcha, Cloudflare challenge, "verify you're human"
text) after navigating. If one is found, execution **pauses and asks the
human at the terminal to solve it in the visible browser window**, then
continues once they press Enter. This is deliberately manual — don't try
to auto-solve CAPTCHAs.

The indicator list in `CAPTCHA_INDICATORS` is a starting set, not
exhaustive. If a specific site uses an unusual challenge that isn't
caught, add a selector for it there — but keep the mechanism generic
(pause for a human) rather than building per-site bypasses.

## Credentials

Never hardcode usernames/passwords in scripts that use this skill. Read
them from environment variables or a secrets manager, one pair per site,
and pass them into `login()` at call time. This skill has no opinion on
*which* storage mechanism to use — that's a separate decision — it just
expects credentials to arrive as plain strings when needed.

## What "generic" means here

Nothing in `browser_agent.py` assumes a specific site's markup, a specific
form layout, or a specific business workflow (comparing prices, adding to
a cart, submitting a form — all just sequences of read → act → verify).
Site-specific logic (which selectors to use, what counts as "success" on
that particular site) belongs in the calling script, not in this skill.
