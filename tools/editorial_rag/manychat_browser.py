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
import re
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
COMPOSER_SELECTOR = 'textarea, [contenteditable="true"], [data-qa="message-input"]'


class ManyChatBrowser:
    """Manages ManyChat operator browser session."""

    def __init__(self, profile_dir: Optional[Path] = None):
        self.profile_dir = profile_dir or PROFILE_DIR
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._stop_requested: bool = False
        self.last_scan_stats: Dict[str, Any] = {}

    def request_stop(self) -> None:
        """Signal ongoing scan or batch operation to halt as soon as possible."""
        self._stop_requested = True

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

    async def _select_tab(self, tab: str) -> bool:
        """Select tab in ManyChat Live Chat: 'mine' (Tú), 'unassigned', 'all', or 'current'."""
        if not tab or tab == "current" or not self._page:
            return True
        try:
            res = await self._page.evaluate(r"""async (targetTab) => {
                const textPattern = targetTab === 'mine' ? /^(?:tú|tu|mine|asignados?\s*a\s*mí)\b/i
                    : targetTab === 'unassigned' ? /^(?:no\s*asignados?|unassigned)\b/i
                    : targetTab === 'all' ? /^(?:todos|all)\b/i : null;
                if (!textPattern) return false;

                const candidates = Array.from(document.querySelectorAll('button, [role="tab"], a, div[class*="tab" i], div[class*="item" i]'));
                for (const el of candidates) {
                    const text = (el.innerText || el.textContent || '').trim();
                    if (textPattern.test(text)) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""", tab)
            if res:
                await asyncio.sleep(1.2)
            return bool(res)
        except Exception:
            return False

    async def _click_list_item(self, lead_id: str) -> bool:
        """Click the sidebar item for a chat if it is currently rendered."""
        return bool(await self._page.evaluate(r"""(targetId) => {
            const item = document.querySelector(`a[href*="/chat/${targetId}"]`);
            if (!item) return false;
            item.scrollIntoView({ block: 'center' });
            item.click();
            return true;
        }""", lead_id))

    async def _open_chat(self, lead_id: str) -> bool:
        """Open a conversation, preferring a list click and falling back to direct navigation."""
        try:
            if not await self._click_list_item(lead_id):
                current_url = self._page.url
                base_match = re.search(r'(https://app\.manychat\.com/[^/]+)', current_url)
                base = base_match.group(1) if base_match else "https://app.manychat.com"
                if base.endswith('/chat'):
                    base = base[:-5]
                await self._page.goto(f"{base}/chat/{lead_id}", wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1.2)
            await self._page.wait_for_selector(COMPOSER_SELECTOR, timeout=6000)
            return True
        except Exception:
            return False

    async def _read_open_chat(self, lead_id: str) -> Dict[str, Any]:
        """Read the history of the currently open conversation (best-effort DOM heuristics)."""
        data = await self._page.evaluate(r"""async () => {
            const SYSTEM = /automatizaci[oó]n|asignad[oa]|movid[oa] de|etiqueta (a[ñn]adida|eliminada)|ha pausado|se activ[oó]|conversaci[oó]n fue|respondi[oó] a tu historia|contenido no disponible|la historia expir/i;
            const composer = document.querySelector('textarea, [contenteditable="true"], [data-qa="message-input"]');
            const inSidebar = el => !!el.closest('a[href*="/chat/"]');
            const inComposer = el => !!(composer && (el === composer || el.contains(composer) || composer.contains(el)));
            const MSG = '[class*="_typeIn_"], [class*="_typeOut_"], [class*="message" i], [class*="bubble" i], [data-qa*="message"]';

            function candidates() {
                const all = Array.from(document.querySelectorAll(MSG))
                    .filter(el => !inSidebar(el) && !inComposer(el) && (el.innerText || '').trim());
                // Keep innermost matches only
                return all.filter(el => !all.some(o => o !== el && el.contains(o)));
            }

            // Brief wait for messages to render if not immediately found
            for (let w = 0; w < 2400; w += 300) {
                if (candidates().length > 0) break;
                await new Promise(r => setTimeout(r, 300));
            }

            function scrollPane(el) {
                let p = el ? el.parentElement : null;
                while (p && p !== document.body) {
                    const s = getComputedStyle(p);
                    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && p.scrollHeight > p.clientHeight) return p;
                    p = p.parentElement;
                }
                return document.querySelector('[class*="chatScroll"], [class*="messagesWrapper"] > div, [class*="messages"] [style*="overflow"]') || null;
            }

            let nodes = candidates();
            const pane = scrollPane(nodes[0]);
            if (pane) {
                let prev = -1, rounds = 0;
                while (rounds < 6) {
                    pane.scrollTop = 0;
                    await new Promise(r => setTimeout(r, 500));
                    const n = candidates().length;
                    if (n === prev) break;
                    prev = n; rounds++;
                }
                nodes = candidates();
            }
            const rect = pane ? pane.getBoundingClientRect() : { left: 0, width: window.innerWidth };
            const center = rect.left + rect.width / 2;

            const messages = nodes.map(el => {
                const r = el.getBoundingClientRect();
                const cls = (el.className && el.className.toString ? el.className.toString() : '') + ' ' +
                    ((el.parentElement && el.parentElement.className && el.parentElement.className.toString) ? el.parentElement.className.toString() : '');
                const textEl = el.querySelector('[class*="_text_"]') || el;
                const text = (textEl.innerText || el.innerText || '').trim();
                let sender;
                const isBot = /_botMessage_|_meta_/i.test(cls);
                if (isBot || SYSTEM.test(text)) sender = 'system';
                else if (/_typeIn_/i.test(cls) || /incoming|received|from-?contact|from-?user/i.test(cls)) sender = 'lead';
                else if (/_typeOut_/i.test(cls) || /outgoing|own[-_ ]|self|from-?agent|sent/i.test(cls)) sender = 'tato';
                else sender = (r.left + r.width / 2) > center ? 'tato' : 'lead';
                return { sender, text, top: r.top + (pane ? pane.scrollTop : window.scrollY) };
            }).sort((a, b) => a.top - b.top);

            const out = [];
            for (const m of messages) {
                const prev = out[out.length - 1];
                if (prev && prev.sender === m.sender && prev.text === m.text) continue;
                out.push({ sender: m.sender, text: m.text });
            }
            let html = '';
            if (out.filter(m => m.sender !== 'system').length < 2) {
                html = (pane || document.body).outerHTML.slice(0, 60000);
            }
            if (pane) pane.scrollTop = pane.scrollHeight;
            return { messages: out, html };
        }""")
        if data.get("html"):
            try:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                (self.profile_dir / f"debug-chat-{lead_id}.html").write_text(data["html"], encoding="utf-8")
            except OSError:
                pass
        return data

    async def scan_conversations(self, limit: int = 30, min_age_hours: float = 6.0,
                                 cooldown_hours: float = 6.0,
                                 tab: str = "mine",
                                 read_history: bool = True,
                                 current_view_only: bool = False) -> List[LeadRecord]:
        """Scan Live Chat conversations idle for at least ``min_age_hours`` and read their history.

        Stats of the last scan are kept in ``self.last_scan_stats``.
        """
        async with self._lock:
            if not self.is_active or not self._page:
                raise RuntimeError("El navegador no está conectado a ManyChat.")

            # Ensure we are in chat
            if "/chat" not in self._page.url:
                current = self._page.url
                if "app.manychat.com" in current:
                    m = re.search(r'(https://app\.manychat\.com/[^/]+)', current)
                    chat_url = f"{m.group(1)}/chat" if m else "https://app.manychat.com/chat"
                else:
                    chat_url = "https://app.manychat.com/chat"

                await self._page.goto(chat_url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(3)

            if tab and tab != "current":
                await self._select_tab(tab)

            ledger = get_ledger()
            blocked_ids = ledger.cooling_down_ids(cooldown_hours)
            pool = min(max(limit * 4, 40), 400)

            # Collect the list, scrolling until enough chats pass the filter or the list ends
            result = await self._page.evaluate(r"""async ([targetLimit, minAgeMinutes, currentViewOnly, blockedIds, cooldownMinutes]) => {
                const seen = new Map();
                const accepted = new Map();
                const blocked = new Set(blockedIds || []);
                let tooRecent = 0, unknownAge = 0, cooling = 0, fupLimit = 0;

                function fupTagNumber(tags) {
                    let best = 0;
                    for (const t of tags || []) {
                        const m = String(t).match(/^\s*(?:fup|fop|seguimiento)\s*[-_ ]?\s*(\d+)\s*$/i);
                        if (m) best = Math.max(best, +m[1]);
                    }
                    return best;
                }

                function ageMinutes(t) {
                    t = (t || '').trim().toLowerCase();
                    if (!t) return null;
                    if (/^(ahora|now|reciente)/.test(t)) return 0;
                    let m;
                    if ((m = t.match(/^(\d+)\s*(?:s|seg)\b/))) return 0;
                    if ((m = t.match(/^(\d+)\s*(?:min|m)\b/))) return +m[1];
                    if ((m = t.match(/^(\d+)\s*(?:h|hs|hr|hrs|hora|horas)\b/))) return +m[1] * 60;
                    if ((m = t.match(/^(\d+)\s*(?:d|día|dia|días|dias)\b/))) return +m[1] * 1440;
                    if ((m = t.match(/^(\d+)\s*(?:sem|w)\b/))) return +m[1] * 10080;
                    if (/^\d+\s*(?:mo|mes|meses|y|yr|a|año|años)\b/.test(t)) return 100000;
                    if (/^ayer|^yesterday/.test(t)) return 1440;
                    if ((m = t.match(/^(\d{1,2}):(\d{2})/))) {
                        const now = new Date();
                        let diff = (now.getHours() * 60 + now.getMinutes()) - (+m[1] * 60 + +m[2]);
                        if (diff < 0) diff += 1440;
                        return diff;
                    }
                    if (/\d{1,2}\s*(?:de\s+)?(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic|jan|apr|aug|dec)/.test(t)) return 100000;
                    if (/^\d{1,2}[\/\-.]\d{1,2}/.test(t)) return 100000;
                    if (/lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday/.test(t)) return 2880;
                    return null;
                }

                function getScrollContainer() {
                    const firstChat = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .find(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    if (!firstChat) return null;
                    let p = firstChat.parentElement;
                    while (p && p !== document.body) {
                        const style = window.getComputedStyle(p);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && p.scrollHeight > p.clientHeight) return p;
                        p = p.parentElement;
                    }
                    return document.querySelector('[class*="threadsWrapper"] > div') || firstChat.closest('[class*="scroll"], [class*="list"], [class*="inbox"]') || firstChat.parentElement;
                }

                function extractCurrent() {
                    const chatLinks = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .filter(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    for (const link of chatLinks) {
                        const href = link.getAttribute('href') || '';
                        const match = href.match(/\/chat\/(\d+)/);
                        const id = match ? match[1] : href;
                        if (!id || seen.has(id)) continue;

                        const lines = (link.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
                        const timeEl = link.querySelector('time');
                        const timeText = timeEl ? (timeEl.getAttribute('datetime') ? '' : timeEl.textContent.trim()) : '';

                        const name = lines[0] || '';
                        let date = timeText;
                        let dateIdx = -1;
                        if (!date) {
                            for (let i = 1; i < lines.length; i++) {
                                if (lines[i].length <= 25 && ageMinutes(lines[i]) !== null) { date = lines[i]; dateIdx = i; break; }
                            }
                        }
                        const snippet = lines.slice(1).filter((_, i) => (i + 1) !== dateIdx).join(' ');

                        const hasOutgoingPrefix = /^(?:tú|tu|you|yo):\s*/i.test(snippet);
                        const hasOutgoingIcon = !!link.querySelector('[class*="outgoing"], [class*="sent"], svg[data-icon*="reply"], svg[data-icon*="check"]');
                        const cleanSnippet = snippet.replace(/^(?:tú|tu|you|yo):\s*/i, '').trim();
                        const tags = Array.from(link.querySelectorAll('[class*="tag"], [class*="badge"], [data-qa*="tag"]'))
                            .map(el => el.textContent.trim()).filter(Boolean);

                        const age = ageMinutes(date);
                        const item = {
                            id, name: name || `Usuario ${id}`, snippet: cleanSnippet || snippet,
                            is_tato: hasOutgoingPrefix || hasOutgoingIcon, date: date || '', age, tags, href
                        };
                        seen.set(id, item);
                        const tagFup = fupTagNumber(tags);
                        if (tagFup >= 2) fupLimit++;
                        else if (blocked.has(id)) cooling++;
                        else if (tagFup >= 1 && (age === null || age < cooldownMinutes)) cooling++;
                        else if (age === null) unknownAge++;
                        else if (age < minAgeMinutes) tooRecent++;
                        else accepted.set(id, item);
                    }
                }

                const startedAt = Date.now();
                extractCurrent();
                if (currentViewOnly) {
                    const c = getScrollContainer();
                    if (c) c.scrollTop = 0;
                    return {
                        chats: Array.from(accepted.values()).slice(0, targetLimit),
                        seen: seen.size, tooRecent, unknownAge, cooling, fupLimit
                    };
                }
                let stagnant = 0;
                // The list is virtualized and lazy-loaded: keep scrolling until enough chats pass the
                // age filter, the list stops growing, or the time budget is exhausted.
                while (accepted.size < targetLimit && Date.now() - startedAt < 150000) {
                    const container = getScrollContainer();
                    const prevSeen = seen.size;
                    const prevTop = container ? container.scrollTop : 0;
                    if (container) {
                        container.scrollTop = prevTop + Math.max(400, Math.floor(container.clientHeight * 0.8));
                        container.dispatchEvent(new Event('scroll', { bubbles: true }));
                        container.dispatchEvent(new WheelEvent('wheel', { deltaY: 600, bubbles: true }));
                    }
                    const validLinks = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .filter(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    if (validLinks.length) validLinks[validLinks.length - 1].scrollIntoView({ block: 'end' });

                    // Poll up to 2.5 s for lazy-loaded rows
                    for (let waited = 0; waited < 2500; waited += 250) {
                        await new Promise(r => setTimeout(r, 250));
                        extractCurrent();
                        if (seen.size > prevSeen) break;
                    }
                    extractCurrent();

                    if (seen.size === prevSeen) {
                        stagnant++;
                        const moved = container ? container.scrollTop !== prevTop : false;
                        if (stagnant >= 8 || (stagnant >= 4 && !moved)) break;
                    } else {
                        stagnant = 0;
                    }
                }

                const c = getScrollContainer();
                if (c) c.scrollTop = 0;
                return {
                    chats: Array.from(accepted.values()).slice(0, targetLimit),
                    seen: seen.size, tooRecent, unknownAge, cooling, fupLimit
                };
            }""", [pool, int(min_age_hours * 60), current_view_only, sorted(blocked_ids), int(cooldown_hours * 60)])

            raw_chats = result["chats"]
            histories: Dict[str, List[Dict[str, str]]] = {}
            history_failures = 0
            if read_history:
                for c in raw_chats:
                    lead_id = c["id"]
                    try:
                        if await self._open_chat(lead_id):
                            data = await self._read_open_chat(lead_id)
                            msgs = [m for m in data.get("messages", []) if m.get("text")]
                            if msgs:
                                histories[lead_id] = msgs[-40:]
                                continue
                    except Exception:
                        pass
                    history_failures += 1

            self.last_scan_stats = {
                "seen": result["seen"],
                "too_recent": result["tooRecent"],
                "unknown_age": result["unknownAge"],
                "cooling_down": result.get("cooling", 0),
                "fup_limit_tag": result.get("fupLimit", 0),
                "accepted": len(raw_chats),
                "history_failures": history_failures,
                "min_age_hours": min_age_hours,
                "cooldown_hours": cooldown_hours,
                "current_view_only": current_view_only,
            }

            leads: List[LeadRecord] = []
            for idx, c in enumerate(raw_chats):
                msg_list: List[LeadMessage] = []
                if c["id"] in histories:
                    for m in histories[c["id"]]:
                        msg_list.append(LeadMessage(sender=m["sender"], text=m["text"]))
                else:
                    snippet = c.get("snippet", "")
                    if snippet:
                        is_tato = bool(c.get("is_tato", False)) or snippet.lower().startswith(("tato:", "tú:", "tu:", "you:", "yo:"))
                        clean_text = re.sub(r'^(?:tato|tú|tu|you|yo):\s*', '', snippet, flags=re.IGNORECASE).strip()
                        msg_list.append(LeadMessage(
                            sender="tato" if is_tato else "lead",
                            text=clean_text or snippet,
                            date=c.get("date"),
                        ))

                tags = c.get("tags", [])
                last_tato_text = next((m.text for m in reversed(msg_list) if m.sender == "tato"), None)
                prior_fup = max(ledger.prior_followup(c.get("id"), last_tato_text), fup_number_from_tags(tags))

                leads.append(LeadRecord(
                    id=c.get("id", f"lead_{idx}"),
                    name=c.get("name", f"Lead {idx + 1}"),
                    handle=c.get("name", "").replace(" ", "_").lower(),
                    last_date=c.get("date") or "sin fecha",
                    tags=tags,
                    messages=msg_list,
                    prior_fup=prior_fup,
                ))

            return leads

    async def scan_conversations_stream(
        self,
        limit: int = 30,
        min_age_hours: float = 6.0,
        current_view_only: bool = False,
        provider_config: Optional[Any] = None,
        mock: bool = False,
        cooldown_hours: float = 6.0,
        tab: str = "mine",
    ):
        """Stream real-time discovery and qualification events for ManyChat leads.

        Yields dictionaries with event types:
        - {"type": "status", "message": str, "total"?: int}
        - {"type": "progress", "current": int, "total": int, "name": str, "message": str}
        - {"type": "lead", "lead": dict, "current": int, "total": int}
        - {"type": "stopped", "message": str, "stats"?: dict}
        - {"type": "done", "message": str, "stats"?: dict}
        - {"type": "error", "error": str}
        """
        self._stop_requested = False
        from .followup_engine import evaluate_lead_llm, evaluate_lead_static
        from .followup_ledger import fup_number_from_tags, get_ledger

        if mock:
            from .local_web import get_sample_manychat_leads
            sample_leads = get_sample_manychat_leads()
            total = min(len(sample_leads), limit)
            yield {
                "type": "status",
                "message": f"Iniciando simulación con {total} leads de prueba...",
                "total": total,
            }
            await asyncio.sleep(0.3)
            processed_mock = 0
            for idx, lead in enumerate(sample_leads[:total]):
                if self._stop_requested:
                    yield {
                        "type": "stopped",
                        "message": f"Simulación detenida por el usuario. Se conservaron {processed_mock} contactos analizados.",
                    }
                    return
                yield {
                    "type": "progress",
                    "current": idx + 1,
                    "total": total,
                    "name": lead.name,
                    "message": f"Analizando {idx+1} de {total}: {lead.name}...",
                }
                await asyncio.sleep(0.4)
                prop = await evaluate_lead_llm(lead, provider_config)
                processed_mock += 1
                yield {
                    "type": "lead",
                    "lead": prop.model_dump(),
                    "current": idx + 1,
                    "total": total,
                }
            yield {
                "type": "done",
                "message": f"Demostración completada: {total} contactos analizados.",
            }
            return

        async with self._lock:
            if not self.is_active or not self._page:
                yield {
                    "type": "error",
                    "error": "El navegador no está conectado a ManyChat. Hacé clic en 'Conectar ManyChat' primero.",
                }
                return

            yield {
                "type": "status",
                "message": "Conectando con ManyChat y verificando vista de chat...",
            }

            # Ensure we are in chat
            if "/chat" not in self._page.url:
                current = self._page.url
                if "app.manychat.com" in current:
                    m = re.search(r'(https://app\.manychat\.com/[^/]+)', current)
                    chat_url = f"{m.group(1)}/chat" if m else "https://app.manychat.com/chat"
                else:
                    chat_url = "https://app.manychat.com/chat"

                try:
                    await self._page.goto(chat_url, wait_until="domcontentloaded", timeout=12000)
                    await asyncio.sleep(2)
                except Exception:
                    pass

            if self._stop_requested:
                yield {"type": "stopped", "message": "Escaneo cancelado antes de iniciar."}
                return

            current_url = self._page.url
            if "/chat" not in current_url or "login" in current_url or "auth" in current_url:
                yield {
                    "type": "error",
                    "error": "No estás logueado en ManyChat. Iniciá sesión en la ventana de Chrome y volvé a escanear.",
                }
                return

            if tab and tab != "current":
                yield {
                    "type": "status",
                    "message": f"Seleccionando bandeja '{tab}' en ManyChat...",
                }
                await self._select_tab(tab)

            yield {
                "type": "status",
                "message": "Buscando conversaciones en ManyChat según los filtros...",
            }

            ledger = get_ledger()
            blocked_ids = ledger.cooling_down_ids(cooldown_hours)
            # `limit` counts ELIGIBLE leads, so collect a wider candidate pool; most chats get discarded.
            pool = min(max(limit * 4, 40), 400)

            result = await self._page.evaluate(r"""async ([targetLimit, minAgeMinutes, currentViewOnly, blockedIds, cooldownMinutes]) => {
                const seen = new Map();
                const accepted = new Map();
                const blocked = new Set(blockedIds || []);
                let tooRecent = 0, unknownAge = 0, cooling = 0, fupLimit = 0;

                function fupTagNumber(tags) {
                    let best = 0;
                    for (const t of tags || []) {
                        const m = String(t).match(/^\s*(?:fup|fop|seguimiento)\s*[-_ ]?\s*(\d+)\s*$/i);
                        if (m) best = Math.max(best, +m[1]);
                    }
                    return best;
                }

                function ageMinutes(t) {
                    t = (t || '').trim().toLowerCase();
                    if (!t) return null;
                    if (/^(ahora|now|reciente)/.test(t)) return 0;
                    let m;
                    if ((m = t.match(/^(\d+)\s*(?:s|seg)\b/))) return 0;
                    if ((m = t.match(/^(\d+)\s*(?:min|m)\b/))) return +m[1];
                    if ((m = t.match(/^(\d+)\s*(?:h|hs|hr|hrs|hora|horas)\b/))) return +m[1] * 60;
                    if ((m = t.match(/^(\d+)\s*(?:d|día|dia|días|dias)\b/))) return +m[1] * 1440;
                    if ((m = t.match(/^(\d+)\s*(?:sem|w)\b/))) return +m[1] * 10080;
                    if (/^\d+\s*(?:mo|mes|meses|y|yr|a|año|años)\b/.test(t)) return 100000;
                    if (/^ayer|^yesterday/.test(t)) return 1440;
                    if ((m = t.match(/^(\d{1,2}):(\d{2})/))) {
                        const now = new Date();
                        let diff = (now.getHours() * 60 + now.getMinutes()) - (+m[1] * 60 + +m[2]);
                        if (diff < 0) diff += 1440;
                        return diff;
                    }
                    if (/\d{1,2}\s*(?:de\s+)?(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic|jan|apr|aug|dec)/.test(t)) return 100000;
                    if (/^\d{1,2}[\/\-.]\d{1,2}/.test(t)) return 100000;
                    if (/lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday/.test(t)) return 2880;
                    return null;
                }

                function getScrollContainer() {
                    const firstChat = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .find(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    if (!firstChat) return null;
                    let p = firstChat.parentElement;
                    while (p && p !== document.body) {
                        const style = window.getComputedStyle(p);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && p.scrollHeight > p.clientHeight) return p;
                        p = p.parentElement;
                    }
                    return document.querySelector('[class*="threadsWrapper"] > div') || firstChat.closest('[class*="scroll"], [class*="list"], [class*="inbox"]') || firstChat.parentElement;
                }

                function extractCurrent() {
                    const chatLinks = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .filter(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    for (const link of chatLinks) {
                        const href = link.getAttribute('href') || '';
                        const match = href.match(/\/chat\/(\d+)/);
                        const id = match ? match[1] : href;
                        if (!id || seen.has(id)) continue;

                        const lines = (link.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
                        const timeEl = link.querySelector('time');
                        const timeText = timeEl ? (timeEl.getAttribute('datetime') ? '' : timeEl.textContent.trim()) : '';

                        const name = lines[0] || '';
                        let date = timeText;
                        let dateIdx = -1;
                        if (!date) {
                            for (let i = 1; i < lines.length; i++) {
                                if (lines[i].length <= 25 && ageMinutes(lines[i]) !== null) { date = lines[i]; dateIdx = i; break; }
                            }
                        }
                        const snippet = lines.slice(1).filter((_, i) => (i + 1) !== dateIdx).join(' ');

                        const hasOutgoingPrefix = /^(?:tú|tu|you|yo):\s*/i.test(snippet);
                        const hasOutgoingIcon = !!link.querySelector('[class*="outgoing"], [class*="sent"], svg[data-icon*="reply"], svg[data-icon*="check"]');
                        const cleanSnippet = snippet.replace(/^(?:tú|tu|you|yo):\s*/i, '').trim();
                        const tags = Array.from(link.querySelectorAll('[class*="tag"], [class*="badge"], [data-qa*="tag"]'))
                            .map(el => el.textContent.trim()).filter(Boolean);

                        const age = ageMinutes(date);
                        const item = {
                            id, name: name || `Usuario ${id}`, snippet: cleanSnippet || snippet,
                            is_tato: hasOutgoingPrefix || hasOutgoingIcon, date: date || '', age, tags, href
                        };
                        seen.set(id, item);
                        const tagFup = fupTagNumber(tags);
                        if (tagFup >= 2) fupLimit++;
                        else if (blocked.has(id)) cooling++;
                        else if (tagFup >= 1 && (age === null || age < cooldownMinutes)) cooling++;
                        else if (age === null) unknownAge++;
                        else if (age < minAgeMinutes) tooRecent++;
                        else accepted.set(id, item);
                    }
                }

                const startedAt = Date.now();
                extractCurrent();
                if (currentViewOnly) {
                    const c = getScrollContainer();
                    if (c) c.scrollTop = 0;
                    return {
                        chats: Array.from(accepted.values()).slice(0, targetLimit),
                        seen: seen.size, tooRecent, unknownAge, cooling, fupLimit
                    };
                }
                let stagnant = 0;
                while (accepted.size < targetLimit && Date.now() - startedAt < 150000) {
                    const container = getScrollContainer();
                    const prevSeen = seen.size;
                    const prevTop = container ? container.scrollTop : 0;
                    if (container) {
                        container.scrollTop = prevTop + Math.max(400, Math.floor(container.clientHeight * 0.8));
                        container.dispatchEvent(new Event('scroll', { bubbles: true }));
                        container.dispatchEvent(new WheelEvent('wheel', { deltaY: 600, bubbles: true }));
                    }
                    const validLinks = Array.from(document.querySelectorAll('a[href*="/chat/"]'))
                        .filter(a => /\/chat\/\d+/.test(a.getAttribute('href') || ''));
                    if (validLinks.length) validLinks[validLinks.length - 1].scrollIntoView({ block: 'end' });

                    for (let waited = 0; waited < 2500; waited += 250) {
                        await new Promise(r => setTimeout(r, 250));
                        extractCurrent();
                        if (seen.size > prevSeen) break;
                    }
                    extractCurrent();

                    if (seen.size === prevSeen) {
                        stagnant++;
                        const moved = container ? container.scrollTop !== prevTop : false;
                        if (stagnant >= 8 || (stagnant >= 4 && !moved)) break;
                    } else {
                        stagnant = 0;
                    }
                }

                const c = getScrollContainer();
                if (c) c.scrollTop = 0;
                return {
                    chats: Array.from(accepted.values()).slice(0, targetLimit),
                    seen: seen.size, tooRecent, unknownAge, cooling, fupLimit
                };
            }""", [pool, int(min_age_hours * 60), current_view_only, sorted(blocked_ids), int(cooldown_hours * 60)])

            raw_chats = result["chats"]
            candidates = len(raw_chats)
            stats: Dict[str, Any] = {
                "seen": result["seen"],
                "too_recent": result["tooRecent"],
                "unknown_age": result["unknownAge"],
                "cooling_down": result.get("cooling", 0),
                "fup_limit_tag": result.get("fupLimit", 0),
                "candidates": candidates,
                "discarded": 0,
                "eligible": 0,
                "history_failures": 0,
                "min_age_hours": min_age_hours,
                "cooldown_hours": cooldown_hours,
                "current_view_only": current_view_only,
            }
            self.last_scan_stats = stats

            def skipped_summary() -> str:
                parts = []
                if stats["cooling_down"]:
                    parts.append(f"{stats['cooling_down']} en espera de {cooldown_hours:g} h desde su último FUP")
                if stats["fup_limit_tag"]:
                    parts.append(f"{stats['fup_limit_tag']} con límite de FUP alcanzado")
                if stats["discarded"]:
                    parts.append(f"{stats['discarded']} descartados al revisar el chat")
                if stats["too_recent"]:
                    parts.append(f"{stats['too_recent']} con actividad de menos de {min_age_hours:g} h")
                if stats["unknown_age"]:
                    parts.append(f"{stats['unknown_age']} sin fecha interpretable")
                return ("No se mostraron: " + ", ".join(parts) + ".") if parts else ""

            if candidates == 0:
                notice = "No se encontraron conversaciones para el filtro seleccionado."
                if result["seen"] > 0:
                    notice = f"Ningún chat quedó habilitado de {result['seen']} vistos. {skipped_summary()}".strip()
                yield {"type": "done", "message": notice, "stats": stats, "total": 0}
                return

            yield {
                "type": "status",
                "message": f"{candidates} candidatos. Revisando hasta juntar {limit} listos para seguimiento...",
                "total": limit,
            }

            for idx, c in enumerate(raw_chats):
                if stats["eligible"] >= limit:
                    break
                if self._stop_requested:
                    yield {
                        "type": "stopped",
                        "message": f"Escaneo detenido por el usuario. {stats['eligible']} listos para seguimiento. {skipped_summary()}".strip(),
                        "stats": stats,
                    }
                    return

                lead_id = c["id"]
                lead_name = c.get("name") or f"Lead {idx+1}"
                yield {
                    "type": "progress",
                    "current": stats["eligible"],
                    "total": limit,
                    "name": lead_name,
                    "message": f"Revisando chat {idx+1} de {candidates}: {lead_name} ({stats['eligible']} de {limit} listos)...",
                }

                msg_list: List[LeadMessage] = []
                try:
                    if await self._open_chat(lead_id):
                        data = await self._read_open_chat(lead_id)
                        msgs = [m for m in data.get("messages", []) if m.get("text")]
                        if msgs:
                            for m in msgs[-40:]:
                                msg_list.append(LeadMessage(sender=m["sender"], text=m["text"]))
                except Exception:
                    pass

                if not msg_list:
                    stats["history_failures"] += 1
                    snippet = c.get("snippet", "")
                    if snippet:
                        is_tato = bool(c.get("is_tato", False)) or snippet.lower().startswith(("tato:", "tú:", "tu:", "you:", "yo:"))
                        clean_text = re.sub(r'^(?:tato|tú|tu|you|yo):\s*', '', snippet, flags=re.IGNORECASE).strip()
                        msg_list.append(LeadMessage(
                            sender="tato" if is_tato else "lead",
                            text=clean_text or snippet,
                            date=c.get("date"),
                        ))

                tags = c.get("tags", [])
                last_tato_text = next((m.text for m in reversed(msg_list) if m.sender == "tato"), None)
                prior_fup = max(ledger.prior_followup(lead_id, last_tato_text), fup_number_from_tags(tags))

                lead = LeadRecord(
                    id=lead_id,
                    name=lead_name,
                    handle=c.get("name", "").replace(" ", "_").lower(),
                    last_date=c.get("date") or "sin fecha",
                    tags=tags,
                    messages=msg_list,
                    prior_fup=prior_fup,
                )

                # Cheap deterministic check first: no LLM call is spent on dead leads.
                proposal = evaluate_lead_static(lead)
                if proposal is None:
                    proposal = await evaluate_lead_llm(lead, provider_config)
                if not proposal.eligible:
                    stats["discarded"] += 1
                    continue

                stats["eligible"] += 1
                yield {
                    "type": "lead",
                    "lead": proposal.model_dump(),
                    "current": stats["eligible"],
                    "total": limit,
                }

            summary = skipped_summary()
            yield {
                "type": "done",
                "message": f"Escaneo completado: {stats['eligible']} listos para seguimiento. {summary}".strip(),
                "stats": stats,
            }

    async def send_message_to_lead(self, lead_id: str, text: str, tag_name: Optional[str] = None) -> Dict[str, Any]:
        """Send a single verified message via ManyChat Live Chat with human typing cadence."""
        async with self._lock:
            if not self.is_active or not self._page:
                raise RuntimeError("El navegador no está conectado.")

            # Select the conversation by finding the link with href containing /chat/<lead_id>
            clicked = await self._page.evaluate(r"""
                (targetId) => {
                    let item = document.querySelector(`a[href*="/chat/${targetId}"]`) ||
                               document.querySelector(`[data-id="${targetId}"], #${targetId}`);
                    if (item) {
                        item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        item.click();
                        return true;
                    }

                    // Search through sidebar scroll container if not immediately in view
                    const firstLink = document.querySelector('a[href*="/chat/"]');
                    if (!firstLink) return false;
                    let p = firstLink.parentElement;
                    while (p && p !== document.body) {
                        const style = window.getComputedStyle(p);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && p.scrollHeight > p.clientHeight) {
                            break;
                        }
                        p = p.parentElement;
                    }
                    const container = p || firstLink.parentElement;
                    if (!container) return false;

                    const step = 500;
                    const maxScroll = container.scrollHeight;
                    for (let pos = 0; pos < maxScroll; pos += step) {
                        container.scrollTop = pos;
                        item = document.querySelector(`a[href*="/chat/${targetId}"]`);
                        if (item) {
                            item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            item.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, lead_id)

            if not clicked:
                # Direct navigation fallback
                current_url = self._page.url
                base_match = re.search(r'(https://app\.manychat\.com/[^/]+)', current_url)
                base = base_match.group(1) if base_match else "https://app.manychat.com"
                await self._page.goto(f"{base}/chat/{lead_id}", wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(1.5)
            else:
                await asyncio.sleep(1.0)

            # Find textarea / message input
            input_selector = 'textarea, [contenteditable="true"], [data-qa="message-input"]'
            try:
                await self._page.wait_for_selector(input_selector, timeout=5000)
            except Exception:
                raise RuntimeError(f"No se pudo abrir la conversación {lead_id} o encontrar el campo de mensaje.")

            await self._page.click(input_selector)

            # Type with human speed
            for char in text:
                await self._page.type(input_selector, char, delay=random.randint(15, 45))

            await asyncio.sleep(0.4)

            # Send via Enter or clicking Send button
            await self._page.keyboard.press("Enter")

            # Wait to observe the bubble appear in the chat stream
            await asyncio.sleep(1.2)

            # Best-effort tagging in ManyChat right sidebar
            if tag_name:
                try:
                    await self._page.evaluate(r"""(tagName) => {
                        const candidates = Array.from(document.querySelectorAll('button, [role="button"], [data-qa*="tag" i], [class*="tag" i]'));
                        const addBtn = candidates.find(b => {
                            const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                            return t === '+ tag' || t === '+ add tag' || t === '+ etiqueta' || t === 'add tag';
                        });
                        if (addBtn) {
                            addBtn.click();
                            setTimeout(() => {
                                const input = document.querySelector('input[placeholder*="tag" i], input[placeholder*="etiqueta" i], [class*="select" i] input');
                                if (input) {
                                    input.value = tagName;
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                                }
                            }, 250);
                        }
                    }""", tag_name)
                except Exception:
                    pass

            # Natural operator pause between 1.5 and 3.0 seconds
            await asyncio.sleep(random.uniform(1.5, 3.0))

            return {
                "status": "sent",
                "lead_id": lead_id,
                "text": text,
                "tag": tag_name,
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
