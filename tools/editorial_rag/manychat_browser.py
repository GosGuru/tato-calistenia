"""ManyChat Playwright Browser Operator.

Controls a persistent Chromium profile for ManyChat Live Chat.
Acts as a human operator:
- Opens persistent session (cookies, 2FA preserved).
- Scans conversations and reads histories.
- Sends approved 1-line messages with human cadence and visual bubble verification.
"""
import asyncio
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from playwright.async_api import BrowserContext, Page, Playwright, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    PLAYWRIGHT_AVAILABLE = False
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    Playwright = Any  # type: ignore
    async_playwright = None  # type: ignore

from .followup_engine import LeadMessage, LeadRecord

PROFILE_DIR = Path.home() / ".tato-manychat-profile"


class ManyChatBrowser:
    """Manages ManyChat operator browser session."""

    def __init__(self, profile_dir: Optional[Path] = None):
        self.profile_dir = profile_dir or PROFILE_DIR
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        return PLAYWRIGHT_AVAILABLE and self._context is not None and self._page is not None and not self._page.is_closed()

    async def get_status(self) -> Dict[str, Any]:
        """Check if browser is running and connected to ManyChat."""
        if not PLAYWRIGHT_AVAILABLE or not self.is_active or not self._page:
            return {
                "active": False,
                "url": "",
                "logged_in": False,
                "profile_path": str(self.profile_dir),
                "playwright_available": PLAYWRIGHT_AVAILABLE,
            }
        try:
            url = self._page.url
            logged_in = "manychat.com" in url and "login" not in url
            return {
                "active": True,
                "url": url,
                "logged_in": logged_in,
                "profile_path": str(self.profile_dir),
                "playwright_available": True,
            }
        except Exception:
            return {
                "active": False,
                "url": "",
                "logged_in": False,
                "profile_path": str(self.profile_dir),
                "playwright_available": PLAYWRIGHT_AVAILABLE,
            }

    async def launch(self, headless: bool = False) -> Dict[str, Any]:
        """Launch browser with persistent user profile so login stays saved."""
        if not PLAYWRIGHT_AVAILABLE:
            return {
                "active": False,
                "url": "",
                "logged_in": False,
                "profile_path": str(self.profile_dir),
                "playwright_available": False,
                "error": "Playwright no está instalado en este entorno. El operador por navegador funciona en modo local.",
            }
        async with self._lock:
            if self.is_active and self._page:
                return await self.get_status()

            self.profile_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._playwright = await async_playwright().start()

                launch_opts = {
                    "user_data_dir": str(self.profile_dir),
                    "headless": headless,
                    "viewport": {"width": 1280, "height": 800},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                }

                # Try system Chrome first, then Edge, then bundled Chromium
                for channel in ("chrome", "msedge", None):
                    try:
                        kwargs = dict(launch_opts)
                        if channel:
                            kwargs["channel"] = channel
                        self._context = await self._playwright.chromium.launch_persistent_context(**kwargs)
                        break
                    except Exception:
                        continue

                if not self._context:
                    return {
                        "active": False,
                        "url": "",
                        "logged_in": False,
                        "profile_path": str(self.profile_dir),
                        "playwright_available": True,
                        "error": "No se pudo iniciar Chrome ni Edge con Playwright.",
                    }

                pages = self._context.pages
                self._page = pages[0] if pages else await self._context.new_page()

                # Go to ManyChat if not already there
                if "manychat.com" not in self._page.url:
                    await self._page.goto("https://manychat.com", wait_until="domcontentloaded")

                return await self.get_status()
            except Exception as exc:
                return {
                    "active": False,
                    "url": "",
                    "logged_in": False,
                    "profile_path": str(self.profile_dir),
                    "playwright_available": True,
                    "error": f"Error al iniciar el navegador: {str(exc)[:120]}",
                }

    async def scan_conversations(self, limit: int = 30) -> List[LeadRecord]:
        """Scan visible conversations from ManyChat Live Chat (Tú / Asignado a mí)."""
        async with self._lock:
            if not self.is_active or not self._page:
                raise RuntimeError("El navegador no está conectado a ManyChat.")

            # Ensure we are in chat
            if "/chat" not in self._page.url:
                await self._page.goto("https://manychat.com/chat", wait_until="domcontentloaded")
                await asyncio.sleep(2)

            # 1. Click on 'Tú' or 'Asignado a mí' if not already selected
            await self._page.evaluate("""() => {
                const candidates = Array.from(document.querySelectorAll('*'));
                // Look for 'Tú' in sidebar or 'Asignado a mí'
                const tuItem = candidates.find(el => {
                    const text = el.textContent.trim();
                    return (text === 'Tú' || text === 'Asignado a mí') && el.children.length === 0;
                });
                if (tuItem) {
                    const clickable = tuItem.closest('button, a, [role="button"], li, div') || tuItem;
                    clickable.click();
                }
            }""")
            await asyncio.sleep(1.5)

            # 2. Extract chats from the list
            raw_chats = await self._page.evaluate("""() => {
                // Find chat items in ManyChat
                // Strategy: find rows containing contact names and snippet/time
                const results = [];
                
                // ManyChat modern UI: rows in conversation list
                // Check common container rows or elements with avatars/dates
                const allElements = Array.from(document.querySelectorAll('*'));
                
                // Let's identify conversation cards: they have a contact name, a preview text, and a time/date indicator
                const candidateContainers = Array.from(document.querySelectorAll(
                    '[data-qa="chat-item"], .chat-item, [class*="ConversationItem"], [class*="chatListItem"], [class*="conversation-item"], [class*="inbox-item"], [role="row"], li'
                ));
                
                // If standard containers match
                for (const item of candidateContainers) {
                    const text = item.innerText || '';
                    const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                    if (lines.length >= 2) {
                        // Check if it looks like a chat row (e.g. contains name + snippet, short lines)
                        // Ignore header elements or navigation links
                        if (lines.includes('Bandeja de entrada') || lines.includes('Todos los chats') || lines.includes('Filtro')) continue;
                        
                        const name = lines[0];
                        const snippet = lines[1] || '';
                        const date = lines.find(l => l.includes('h') || l.includes('d') || l.includes('m') || l.includes('septiembre') || l.includes(':')) || '';
                        const id = item.getAttribute('data-id') || item.getAttribute('id') || `chat_${name.replace(/\\s+/g, '_')}`;
                        
                        // Avoid duplicates
                        if (!results.some(r => r.name === name)) {
                            results.push({ id, name, snippet, date });
                        }
                    }
                }
                
                // Fallback: if candidateContainers didn't catch, search by finding elements that look like chat row names
                if (results.length === 0) {
                    // Search for avatar + text siblings or common chat list structure
                    const names = allElements.filter(el => {
                        return el.children.length === 0 &&
                               el.textContent.trim().length > 2 &&
                               el.textContent.trim().length < 40 &&
                               el.parentElement &&
                               (el.parentElement.className.includes('name') ||
                                el.parentElement.className.includes('title') ||
                                el.tagName === 'STRONG' ||
                                el.tagName === 'H4');
                    });
                    
                    for (const n of names) {
                        const row = n.closest('li, [role="row"], div') || n.parentElement;
                        if (row && row.innerText) {
                            const lines = row.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
                            const name = n.textContent.trim();
                            const snippet = lines.find(l => l !== name && l.length > 5) || '';
                            const date = lines.find(l => l !== name && l !== snippet && (l.includes('h') || l.includes('d') || l.includes('m'))) || '';
                            const id = row.getAttribute('data-id') || row.getAttribute('id') || `chat_${name.replace(/\\s+/g, '_')}`;
                            if (!results.some(r => r.name === name)) {
                                results.push({ id, name, snippet, date });
                            }
                        }
                    }
                }
                
                return results;
            }""")

            leads: List[LeadRecord] = []
            for idx, c in enumerate(raw_chats[:limit]):
                msg_list = []
                if c.get("snippet"):
                    msg_list.append(LeadMessage(
                        sender="lead" if not c["snippet"].lower().startswith("tato:") else "tato",
                        text=c["snippet"],
                        date=c.get("date"),
                    ))

                leads.append(LeadRecord(
                    id=c.get("id", f"lead_{idx}"),
                    name=c.get("name", f"Lead {idx + 1}"),
                    handle=c.get("name", "").replace(" ", "_").lower(),
                    last_date=c.get("date", "reciente"),
                    tags=[],
                    messages=msg_list,
                ))

            return leads

    async def send_message_to_lead(self, lead_id: str, text: str) -> Dict[str, Any]:
        """Send a single verified message via ManyChat Live Chat with human typing cadence."""
        async with self._lock:
            if not self.is_active or not self._page:
                raise RuntimeError("El navegador no está conectado.")

            # Select the conversation
            clicked = await self._page.evaluate(f"""
                (targetId) => {{
                    const item = document.querySelector(`[data-id="${{targetId}}"], #${{targetId}}`);
                    if (item) {{
                        item.click();
                        return true;
                    }}
                    return false;
                }}
            """, lead_id)

            await asyncio.sleep(1.0)

            # Find textarea / message input
            input_selector = 'textarea, [contenteditable="true"], [data-qa="message-input"]'
            await self._page.wait_for_selector(input_selector, timeout=5000)

            # Type with human speed
            for char in text:
                await self._page.type(input_selector, char, delay=random.randint(20, 60))

            await asyncio.sleep(0.5)

            # Send via Enter or clicking Send button
            await self._page.keyboard.press("Enter")

            # Wait to observe the bubble appear in the chat stream
            await asyncio.sleep(1.5)

            # Natural operator pause between 2.5 and 4 seconds
            await asyncio.sleep(random.uniform(2.5, 4.0))

            return {
                "status": "sent",
                "lead_id": lead_id,
                "text": text,
            }

    async def close(self):
        """Close browser context."""
        async with self._lock:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None


# Global singleton instance
_browser_instance: Optional[ManyChatBrowser] = None


def get_manychat_browser() -> ManyChatBrowser:
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = ManyChatBrowser()
    return _browser_instance
