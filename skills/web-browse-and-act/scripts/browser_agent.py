#!/usr/bin/env python3
"""
Generic web browsing + action-taking, for any website.

Not tied to any specific supplier, form, or page structure. Provides the
primitives an agent needs to work against an arbitrary site: load a page,
read what's actually on it, click things, fill forms, log in, detect and
pause for CAPTCHAs, and verify that an action actually took effect instead
of trusting that a click succeeded.

Built on Playwright (not Selenium) because it has better auto-waiting and
a much saner API for this kind of scripted interaction.

Usage as a library:
    from browser_agent import WebAgent

    agent = WebAgent(headless=False)  # headless=False so a human can see/help
    agent.goto("https://example.com/login")
    agent.login(
        username_selector="#email", password_selector="#password",
        submit_selector="button[type=submit]",
        username="me@example.com", password="hunter2",
    )
    agent.fill("#search", "widget X")
    agent.click("button.search-submit")
    print(agent.read_page())
    agent.click("text=Add to cart")
    agent.verify_text_present("Added to cart")  # don't trust the click alone
    agent.close()

Usage as a CLI (for quick one-off checks, not full workflows):
    python browser_agent.py goto https://example.com
    python browser_agent.py read https://example.com

Requires:
    pip install playwright
    playwright install chromium
"""
import re
import sys
import time


# Heuristics for detecting a CAPTCHA / bot-check on a page. Not exhaustive —
# extend this list if a specific site uses something unusual, but keep the
# check itself generic rather than hardcoding one vendor's markup.
CAPTCHA_INDICATORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[title*='challenge']",
    "div.g-recaptcha",
    "div.h-captcha",
    "#cf-challenge-running",  # Cloudflare
    "text=/verify you are human/i",
    "text=/are you a robot/i",
    "text=/select all images/i",
]


class WebAgent:
    def __init__(self, headless=False, slow_mo_ms=0, user_data_dir=None):
        """
        headless=False by default: this agent is meant to hand control back
        to a human (e.g. to solve a CAPTCHA) and that only works with a
        visible browser window.

        user_data_dir: pass a persistent profile directory to keep cookies/
        login sessions between runs, instead of starting fresh every time.
        """
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        if user_data_dir:
            self.context = self._playwright.chromium.launch_persistent_context(
                user_data_dir, headless=headless, slow_mo=slow_mo_ms,
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.browser = None
        else:
            self.browser = self._playwright.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

    # ---- navigation ----

    def goto(self, url, wait_until="load"):
        self.page.goto(url, wait_until=wait_until)
        self._pause_for_captcha_if_present()
        return self.page.url

    def reload(self):
        self.page.reload()
        self._pause_for_captcha_if_present()

    # ---- reading the page ----

    def read_page(self, max_chars=8000):
        """
        Returns the visible text content of the page, trimmed to a
        reasonable size. This is the generic way to 'see' what's on a page
        before deciding what to click/fill next.
        """
        text = self.page.inner_text("body")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:max_chars]

    def list_interactive_elements(self, limit=50):
        """
        Returns a rough map of clickable/fillable elements on the page —
        useful for figuring out selectors when you don't already know the
        page's structure. Each entry: {tag, text, selector_hint}.
        """
        elements = self.page.eval_on_selector_all(
            "button, a, input, select, textarea",
            """els => els.slice(0, %d).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 80),
                id: el.id || '',
                name: el.getAttribute('name') || '',
            }))""" % limit,
        )
        return elements

    def screenshot(self, path):
        self.page.screenshot(path=path, full_page=True)
        return path

    # ---- acting on the page ----

    def click(self, selector, timeout_ms=10_000):
        """
        `selector` accepts CSS, or Playwright's `text=...` syntax for
        clicking by visible text (e.g. `text=Add to cart`), which is
        usually more robust than guessing CSS classes on unfamiliar sites.
        """
        self.page.click(selector, timeout=timeout_ms)
        self._pause_for_captcha_if_present()

    def fill(self, selector, value, timeout_ms=10_000):
        self.page.fill(selector, value, timeout=timeout_ms)

    def fill_form(self, fields: dict, submit_selector=None):
        """
        fields: {selector: value}. Fills each field in order, then
        optionally clicks a submit selector.
        """
        for selector, value in fields.items():
            self.fill(selector, value)
        if submit_selector:
            self.click(submit_selector)

    def select_option(self, selector, value):
        self.page.select_option(selector, value)

    def login(self, username_selector, password_selector, submit_selector,
               username, password):
        """
        Generic login helper — works for any site with a standard
        username+password+submit form. For sites with multi-step logins
        (e.g. email first, then password on a second screen), call `fill`
        and `click` directly instead of this helper.
        """
        self.fill(username_selector, username)
        self.fill(password_selector, password)
        self.click(submit_selector)

    # ---- verification (don't trust that a click "worked") ----

    def verify_text_present(self, expected_text, timeout_ms=10_000):
        """
        Waits for the given text to appear anywhere on the page. Use this
        after actions like "add to cart" instead of assuming the click
        succeeded — check the actual resulting state.
        """
        try:
            self.page.wait_for_selector(f"text={expected_text}", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def verify_on_url(self, url_substring, timeout_ms=10_000):
        """Waits until the current URL contains the given substring."""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if url_substring in self.page.url:
                return True
            time.sleep(0.2)
        return False

    # ---- CAPTCHA handling ----

    def _pause_for_captcha_if_present(self):
        if not self.detect_captcha():
            return
        print(
            "\n*** CAPTCHA / bot-check detected on this page. ***\n"
            "Please solve it manually in the browser window, then press "
            "Enter here to continue.\n"
        )
        input("Press Enter once solved... ")
        # Give the page a moment to settle after the challenge is cleared.
        self.page.wait_for_timeout(1500)

    def detect_captcha(self):
        for indicator in CAPTCHA_INDICATORS:
            try:
                if self.page.locator(indicator).count() > 0:
                    return True
            except Exception:
                continue
        return False

    # ---- cleanup ----

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            else:
                self.context.close()
        finally:
            self._playwright.stop()


def _cli():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command, url = sys.argv[1], sys.argv[2]
    agent = WebAgent(headless=False)
    try:
        agent.goto(url)
        if command == "read":
            print(agent.read_page())
        elif command == "elements":
            for el in agent.list_interactive_elements():
                print(el)
        elif command == "goto":
            print(f"Loaded: {agent.page.url}")
        else:
            print(f"Unknown command: {command}")
    finally:
        input("\nPress Enter to close the browser...")
        agent.close()


if __name__ == "__main__":
    _cli()
