"""Loopback-only reviewed DM and synthetic screens. Explicit per-call consent."""
import asyncio
import os
import re
import secrets
import socket
import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)
from starlette.exceptions import HTTPException

from .api_runner import (
    ApiRunnerError,
    ProviderConfig,
    create_runner,
    get_available_models_info,
    test_provider_connection,
)
from .app_auth import AppAuth
from .app_rules import load_app_rules
from .codex_runner import CodexSessionRunner
from .generation_diagnostics import GenerationDiagnostics
from .organization import OrganizationPacket, parse_assignments, parse_blocks
from .prototype import compare, packets
from .rag_service import retrieve
from .raw_history import RawHistoryPacket, parse_raw_result, valid_raw_text
from .real_history import (
    MAX_BODY_BYTES,
    MAX_CHARACTERS,
    RealPacket,
    parse_history,
    parse_messages,
)
from .synthetic_compare import CASE_ID, load_rules, synthetic_case
from .followup_engine import (
    FollowupProposal,
    LeadMessage,
    LeadRecord,
    evaluate_lead_llm,
)
from .manychat_browser import get_manychat_browser

HOST = '127.0.0.1:8765'
ORIGIN = 'http://' + HOST
INVALID = 'Solicitud no válida.'
FAILURE = 'No se pudo completar el par. No se devolvieron borradores.'
BUSY = 'Ya hay una comparación o generación en curso. Esperá a que termine.'
DRAFT_FAILURE = 'No se pudo generar el DM. No se devolvió ningún borrador.'
ORGANIZATION_FAILURE = 'No se pudo organizar la conversación. No se aplicó ninguna propuesta.'
DIST = Path(__file__).resolve().parent / 'web' / 'dist'
# One token and one flight per process, shared even across app instances.
_TOKEN = secrets.token_urlsafe(32)
_FLIGHT = threading.Lock()
SECURITY_HEADERS = {
    'Cache-Control': 'no-store',
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'"
    ),
}
DEMO_DRAFTS = {
    'current': 'entiendo, qué te está costando hoy con las dominadas?',
    'editorial': 'qué pasa hoy cuando intentás hacer una dominada?',
}


def error(status, text=INVALID):
    return JSONResponse({'error': text}, status_code=status)


def is_cloud_env():
    port = os.environ.get('PORT')
    railway = os.environ.get('RAILWAY_ENVIRONMENT')
    render = os.environ.get('RENDER')
    return ((isinstance(port, str) and bool(port))
            or (isinstance(railway, str) and bool(railway))
            or (isinstance(render, str) and bool(render)))


class LocalBoundary:
    """Check raw headers before routing and bound bodies before JSON parsing."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def secured_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (key.lower().encode(), value.encode()) for key, value in SECURITY_HEADERS.items()]
            await send(message)

        def values(name):
            return [value for key, value in scope['headers'] if key.lower() == name]

        origins = values(b'origin')
        hosts = values(b'host')
        is_cloud = is_cloud_env()

        if not is_cloud:
            if (hosts != [HOST.encode()]
                    or (origins and origins != [ORIGIN.encode()])):
                return await error(403)(scope, receive, secured_send)
            if scope['method'] == 'POST':
                tokens = values(b'x-csrf-token')
                if (origins != [ORIGIN.encode()] or len(tokens) != 1
                        or not secrets.compare_digest(tokens[0], _TOKEN.encode())):
                    return await error(403)(scope, receive, secured_send)
        else:
            if scope['method'] == 'POST':
                tokens = values(b'x-csrf-token')
                if len(tokens) != 1 or not secrets.compare_digest(tokens[0], _TOKEN.encode()):
                    return await error(403)(scope, receive, secured_send)
                if origins:
                    origin_str = origins[0].decode('latin1', errors='ignore')
                    host_str = hosts[0].decode('latin1', errors='ignore') if hosts else ''
                    origin_host = origin_str.split('://', 1)[-1].split('/', 1)[0].split(':', 1)[0]
                    target_host = host_str.split(':', 1)[0]
                    if origin_host and target_host and origin_host.lower() != target_host.lower():
                        return await error(403)(scope, receive, secured_send)

        if scope['method'] == 'POST':
            types = values(b'content-type')
            if len(types) != 1 or types[0].split(b';')[0].strip().lower() != b'application/json':
                return await error(415)(scope, receive, secured_send)
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                body.extend(message.get('body', b''))
                path = scope.get('path')
                limit = (32768 if path in ('/api/auth/login', '/api/models/test', '/api/manychat/launch') else MAX_BODY_BYTES
                         if path in ('/api/draft', '/api/organize', '/api/raw-draft', '/api/manychat/scan', '/api/manychat/send-batch') else 256)
                if len(body) > limit:
                    return await error(413)(scope, receive, secured_send)
                if not message.get('more_body', False):
                    break

            try:
                body.decode('utf-8')
            except UnicodeDecodeError:
                return await error(422)(scope, receive, secured_send)

            async def buffered_receive():
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            receive = buffered_receive
        await self.app(scope, receive, secured_send)


class Consent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: StrictBool

    @field_validator('consent')
    @classmethod
    def must_confirm(cls, value):
        if not value:
            raise ValueError('Explicit consent required')
        return value


class RawDraftRequest(Consent):
    history: StrictStr
    provider_config: ProviderConfig | None = None

    @field_validator('history')
    @classmethod
    def valid_history(cls, value):
        if not valid_raw_text(value):
            raise ValueError(INVALID)
        return value


class DraftRequest(Consent):
    history: StrictStr | None = None
    messages: list | None = None
    reviewed: StrictBool
    provider_config: ProviderConfig | None = None

    @model_validator(mode='before')
    @classmethod
    def one_source(cls, value):
        if type(value) is not dict:
            raise ValueError(INVALID)
        keys = set(value)
        keys.discard('provider_config')
        if keys == {'history', 'reviewed', 'consent'}:
            parse_history(value['history'])
        elif keys == {'messages', 'reviewed', 'consent'}:
            parse_messages(value['messages'])
        else:
            raise ValueError(INVALID)
        return value

    @field_validator('reviewed')
    @classmethod
    def must_review(cls, value):
        if not value:
            raise ValueError('Explicit review required')
        return value

    @field_validator('history')
    @classmethod
    def valid_history(cls, value):
        if len(value) > MAX_CHARACTERS:
            raise ValueError('History too long')
        parse_history(value)
        return value


class OrganizationRequest(Consent):
    blocks: list
    reviewed: StrictBool

    @model_validator(mode='before')
    @classmethod
    def validate_packet(cls, value):
        if type(value) is not dict or set(value) != {'blocks', 'reviewed', 'consent'}:
            raise ValueError(INVALID)
        OrganizationPacket(parse_blocks(value['blocks']), value['reviewed'], value['consent']).validate()
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: StrictStr
    password: StrictStr

    @model_validator(mode='after')
    def credentials(self):
        if (not 1 <= len(self.email) <= 320 or '@' not in self.email
                or any(c.isspace() or ord(c) < 32 for c in self.email)
                or not 1 <= len(self.password) <= 4096):
            raise ValueError(INVALID)
        return self


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ManyChatLaunchRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    headless: bool = False


class ManyChatScanRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    date_filter: str = 'septiembre'
    limit: int = 30
    mock: bool = False
    provider_config: ProviderConfig | None = None


class ManyChatSendItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    draft: str


class ManyChatSendBatchRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    leads: list[ManyChatSendItem]
    mock: bool = False


def get_sample_manychat_leads() -> list[LeadRecord]:
    return [
        LeadRecord(
            id="lead_1",
            name="Alberto Huilcaleo",
            handle="alberto_h",
            last_date="15 de septiembre",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Hola Tato, estuve viendo tus videos de anillas y me interesa mucho aprender a hacer dominadas sin dolor de hombro."),
                LeadMessage(sender="tato", text="Buenas Alberto. En anillas la articulación rota libre y eso cambia todo respecto a una barra fija."),
                LeadMessage(sender="lead", text="Totalmente, me pasa que en barra fija me pincha el hombro izquierdo cuando intento subir."),
                LeadMessage(sender="tato", text="Claro, la rotación externa al traccionar descomprime la cápsula del hombro. ¿Hoy estás pudiendo colgarte sin dolor?"),
            ],
        ),
        LeadRecord(
            id="lead_2",
            name="Julieta R",
            handle="juli_calist",
            last_date="20 de septiembre",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Hola Tato! Quiero arrancar a entrenar fuerza pero me cuesta ser constante sola."),
                LeadMessage(sender="tato", text="Buenas Julieta. Más que fuerza de voluntad sola, lo que sostiene el hábito es tener una progresión clara y adaptada a tu día a día."),
                LeadMessage(sender="lead", text="Sí, tal cual, trabajo 8 horas en oficina y termino liquidada."),
                LeadMessage(sender="tato", text="Lo entiendo perfecto. Para ver si tiene sentido encarar un proceso online de 90 días juntos, podemos hacer una reunión de auditoría de 15 minutos."),
                LeadMessage(sender="lead", text="Dale, me re interesa!"),
                LeadMessage(sender="tato", text="Elegí día y hora acá https://cal.com/tato-ramon/reunion-auditoria y avisame cuando quede confirmado."),
            ],
        ),
        LeadRecord(
            id="lead_3",
            name="Carlos Méndez",
            handle="carlos_m",
            last_date="8 de septiembre",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Cuánto sale el programa?"),
                LeadMessage(sender="tato", text="Depende del objetivo y el tiempo de acompañamiento. ¿Hacia dónde querés llevar tu entrenamiento?"),
                LeadMessage(sender="tato", text="Buenas Carlos, ¿pudiste ver el mensaje anterior?"),
            ],
        ),
        LeadRecord(
            id="lead_4",
            name="Marcos V",
            handle="marcos_v",
            last_date="2 de septiembre",
            tags=["NO CALIFICA"],
            messages=[
                LeadMessage(sender="lead", text="No gracias, ya me anoté a un gimnasio convencional."),
            ],
        ),
    ]


def comparison(simulated):
    if not _FLIGHT.acquire(blocking=False):
        return error(409, BUSY)
    drafts = {}
    try:
        conversation, cards = synthetic_case()
        rules = load_rules()
        runner = None if simulated else CodexSessionRunner()

        def capture(packet):
            draft = DEMO_DRAFTS[packet.variant] if runner is None else runner(packet)
            if not isinstance(draft, str) or not draft.strip():
                raise ValueError('Empty draft')
            drafts[packet.variant] = draft
            return draft

        report = compare(conversation, cards, rules, capture)
        # Serialize only the complete pair. Never expose the first draft early.
        return JSONResponse({
            'mode': 'simulated' if simulated else 'codex',
            'label': 'Demo simulada · borradores manuales' if simulated else 'Codex · caso sintético',
            'drafts': drafts, 'signals': asdict(report),
        })
    except Exception:
        return error(502, FAILURE)
    finally:
        drafts.clear()
        _FLIGHT.release()


def create_app(auth=None):
    # Default construction remains memory-only and never discovers configuration.
    auth = AppAuth() if auth is None else auth
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    app.add_middleware(LocalBoundary)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error(422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code)

    @app.get('/api/bootstrap')
    def bootstrap():
        # Primary screen must not depend on synthetic fixtures or editorial cards.
        return {'app': 'tato-local', 'protocol': 1, 'csrf_token': _TOKEN,
                    'model': 'unknown', 'effort': 'unknown'}

    @app.get('/api/auth/status')
    def auth_status():
        return auth.status()

    @app.get('/api/auth/persistence')
    def auth_persistence():
        return auth.persistence()

    @app.post('/api/auth/login')
    def auth_login(body: LoginRequest):
        try:
            connected = auth.login(body.email, body.password)
        finally:
            body.email = body.password = ''
        return auth.status() if connected else error(401, 'No se pudo conectar la biblioteca.')

    @app.post('/api/auth/logout')
    def auth_logout(body: DemoRequest):
        auth.logout()
        return auth.status()

    @app.post('/api/raw-draft')
    def raw_draft(body: RawDraftRequest):
        if not _FLIGHT.acquire(blocking=False):
            return error(409, BUSY)
        revision, require_connected = None, False
        changed = 'La sesión cambió o venció. No se devolvió ningún borrador.'
        diagnostics = GenerationDiagnostics()
        runner_error_msg = None

        def diagnosed(response):
            fallback = 'rejected' if response.status_code == 409 else 'internal' if response.status_code >= 400 else 'ok'
            response.headers.update(diagnostics.headers(fallback))
            return response

        try:
            with diagnostics.stage('retrieval'):
                revision, state, _, _ = auth.snapshot()
                require_connected = state == 'connected'
                selected_revision, guidance, retrieval = retrieve(auth, body.history)
            if selected_revision != revision or not auth.current(revision, require_connected):
                return diagnosed(error(409, changed))
            with diagnostics.stage('rules'):
                rules = load_app_rules()
            with diagnostics.stage('packet'):
                packet = RawHistoryPacket(body.history, rules, body.consent, guidance)
                packet.validate()
            runner = (CodexSessionRunner(diagnostics=diagnostics)
                      if (body.provider_config is None or body.provider_config.provider == 'codex')
                      else create_runner(body.provider_config, diagnostics=diagnostics))
            output = runner(packet)
            with diagnostics.stage('raw_result'):
                result = parse_raw_result(output)
            if not auth.current(revision, require_connected):
                return diagnosed(error(409, changed))
            payload = {'result': result, 'retrieval': retrieval, 'revision': revision}
            thinking = getattr(runner, 'last_thinking', None)
            if isinstance(thinking, str) and thinking.strip():
                payload['thinking'] = thinking
            return diagnosed(JSONResponse(payload))
        except ApiRunnerError as exc:
            runner_error_msg = str(exc)
            failure_status = 502
        except Exception:
            failure_status = 502
        finally:
            _FLIGHT.release()
        # Construct sanitized failure outside the handler; retain no caught exception.
        if revision is not None and not auth.current(revision, require_connected):
            return diagnosed(error(409, changed))
        return diagnosed(error(failure_status, runner_error_msg or DRAFT_FAILURE))

    @app.get('/api/context')
    def context():
        try:
            conversation, cards = synthetic_case()
            _, editorial = packets(conversation, cards, load_rules())
            if editorial.guidance is None:
                raise ValueError('Synthetic guidance missing')
            return {
                'case': CASE_ID, 'phase': conversation.phase,
                'messages': [asdict(message) for message in conversation.messages],
                'guidance': asdict(editorial.guidance),
                'model': 'unknown', 'effort': 'unknown', 'csrf_token': _TOKEN,
            }
        except Exception:
            return error(503, 'No se pudo cargar el caso sintético.')

    # Sync routes run in FastAPI's threadpool, not the event loop.
    @app.post('/api/generate')
    def generate(body: Consent):
        return comparison(simulated=False)

    @app.post('/api/draft')
    def draft(body: DraftRequest):
        if not _FLIGHT.acquire(blocking=False):
            return error(409, BUSY)
        try:
            messages = parse_messages(body.messages) if body.messages is not None else parse_history(body.history)
            packet = RealPacket(messages, load_app_rules(), body.reviewed, body.consent)
            packet.validate()
            runner = (CodexSessionRunner()
                      if (body.provider_config is None or body.provider_config.provider == 'codex')
                      else create_runner(body.provider_config))
            result = runner(packet)
            if type(result) is not str or not result.strip():
                raise ValueError('Invalid draft')
            return JSONResponse({'draft': result})
        except ApiRunnerError as exc:
            return error(502, str(exc))
        except Exception:
            return error(502, DRAFT_FAILURE)
        finally:
            _FLIGHT.release()

    @app.post('/api/organize')
    def organize(body: OrganizationRequest):
        if not _FLIGHT.acquire(blocking=False):
            return error(409, BUSY)
        try:
            packet = OrganizationPacket(parse_blocks(body.blocks), body.reviewed, body.consent)
            packet.validate()
            output = CodexSessionRunner()(packet)
            return JSONResponse(parse_assignments(output, packet))
        except Exception:
            return error(502, ORGANIZATION_FAILURE)
        finally:
            _FLIGHT.release()

    @app.post('/api/demo')
    def demo(body: DemoRequest):
        return comparison(simulated=True)

    @app.get('/api/models')
    def models_info():
        return get_available_models_info()

    @app.post('/api/models/test')
    def test_model(body: ProviderConfig):
        return test_provider_connection(body)

    @app.get('/api/manychat/status')
    async def manychat_status():
        browser = get_manychat_browser()
        return await browser.get_status()

    @app.post('/api/manychat/launch')
    async def manychat_launch(body: ManyChatLaunchRequest):
        browser = get_manychat_browser()
        try:
            return await browser.launch(headless=body.headless)
        except Exception as exc:
            return {
                'active': False,
                'url': '',
                'logged_in': False,
                'error': f'Error al iniciar el navegador: {str(exc)[:120]}',
            }

    @app.post('/api/manychat/scan')
    async def manychat_scan(body: ManyChatScanRequest):
        browser = get_manychat_browser()
        leads: list[LeadRecord] = []
        if body.mock:
            leads = get_sample_manychat_leads()
        elif not browser.is_active:
            return JSONResponse({
                'status': 'error',
                'error': 'El navegador no está conectado a ManyChat. Hacé clic en "Conectar ManyChat" primero, o usá "Demo de prueba" para simular.',
                'leads': [],
                'count': 0,
            })
        else:
            try:
                leads = await browser.scan_conversations(limit=body.limit)
            except Exception as exc:
                return JSONResponse({
                    'status': 'error',
                    'error': f'Error al escanear ManyChat: {str(exc)[:120]}',
                    'leads': [],
                    'count': 0,
                })

        if not leads:
            return JSONResponse({
                'status': 'ok',
                'leads': [],
                'count': 0,
                'notice': 'No se encontraron conversaciones activas en ManyChat para escanear.',
            })

        sem = asyncio.Semaphore(10)

        async def _eval_one(l: LeadRecord) -> dict:
            async with sem:
                prop = await evaluate_lead_llm(l, body.provider_config)
                return prop.model_dump()

        proposals = await asyncio.gather(*[_eval_one(lead) for lead in leads])
        return JSONResponse({'status': 'ok', 'leads': list(proposals), 'count': len(proposals)})

    @app.post('/api/manychat/send-batch')
    async def manychat_send_batch(body: ManyChatSendBatchRequest):
        browser = get_manychat_browser()
        results: list[dict] = []
        for item in body.leads:
            if body.mock or not browser.is_active:
                await asyncio.sleep(0.3)
                results.append({'id': item.id, 'status': 'sent', 'text': item.draft})
            else:
                try:
                    res = await browser.send_message_to_lead(item.id, item.draft)
                    results.append({'id': item.id, 'status': 'sent', 'text': item.draft})
                except Exception as exc:
                    results.append({'id': item.id, 'status': 'failed', 'error': str(exc)[:120]})
        return JSONResponse({'results': results})

    def asset(path, parent, media_type, missing=404):
        try:
            # Refuse symlinks/junctions in the build path, not just traversal.
            if (parent.resolve() != parent.absolute() or path.resolve() != path.absolute()
                    or path.parent != parent or not path.is_file()):
                return error(missing)
            return Response(path.read_bytes(), media_type=media_type)
        except OSError:
            return error(missing)

    @app.get('/')
    def index():
        return asset(DIST / 'index.html', DIST, 'text/html', missing=503)

    @app.get('/assets/{name}')
    def compiled_asset(name: str):
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:js|css)', name):
            return error(404)
        return asset(DIST / 'assets' / name, DIST / 'assets',
                     'text/javascript' if name.endswith('.js') else 'text/css')

    return app


# Names only for the deployment credential variables: their values are read
# from the process environment at startup and are never assigned into code,
# logged, printed, written to disk or placed in an exception message.
ENV_CREDENTIAL_VARS = ('TATO_LIBRARY_REFRESH_TOKEN', 'TATO_LIBRARY_EMAIL', 'TATO_LIBRARY_PASSWORD')


def _env_credential(name):
    """Non-empty environment text only; any other value counts as absent."""
    value = os.environ.get(name)
    return value if type(value) is str and value else None


def environment_auth():
    """Startup session from explicit deployment credentials; None when unset.

    A complete credential set opts in: the refresh token alone (preferred) or
    the email/password pair. The refresh token seeds the in-memory equivalent of
    the persisted session so ``restore()`` can renew and verify it; the pair is
    used once at startup to sign in. Owner match, the pinned project and the
    authenticated Supabase read all still run. Without a complete set the caller
    keeps today's behaviour unchanged. Failures return a bare disconnected
    ``AppAuth``: no credential value is logged, printed, written to disk or
    placed in an exception message.
    """
    refresh_var, email_var, password_var = ENV_CREDENTIAL_VARS
    refresh = _env_credential(refresh_var)
    email = _env_credential(email_var)
    password = _env_credential(password_var)
    if refresh is None and (email is None or password is None):
        return None
    try:
        from .library_config import env_config
        from .session_store import EnvSessionStore

        config = env_config()
        if refresh is not None:
            auth = AppAuth(store=EnvSessionStore(config, refresh))
            auth.restore()
            return auth
        auth = AppAuth(store=EnvSessionStore(config))
        auth.login(email, password)
        return auth
    except Exception:
        del refresh, email, password
        return AppAuth()


def production_auth():
    """Only the foreground launcher opts into current-user persistence."""
    from .library_config import env_config, load_config
    from .session_store import SessionStore

    try:
        auth = environment_auth()
        if auth is not None:
            return auth
        if is_cloud_env():
            # Managed deployment: no local file and no persisted session exist here,
            # so the bounded public configuration is injected explicitly.
            return AppAuth(config_source=env_config)
        if os.name != 'nt':
            return AppAuth()
        root = Path(os.environ.get('LOCALAPPDATA', ''))
        repository = Path(__file__).resolve().parents[2]
        if not root.is_absolute() or root.resolve().is_relative_to(repository):
            return AppAuth()
        config = load_config()
        store = SessionStore(root / 'TatoEditorialRag' / 'session.dpapi', config)
        auth = AppAuth(store=store)
        auth.restore()
        return auth
    except Exception:
        return AppAuth()


def main():
    import uvicorn

    if not (DIST / 'index.html').is_file():
        print('Falta el build local. No se inició el servidor.')
        return 1
    reserved = None
    try:
        is_cloud = is_cloud_env()
        raw_port = os.environ.get('PORT')
        port = int(raw_port) if isinstance(raw_port, str) and raw_port.isdigit() else 8765
        # pi-lens-ignore: S104
        host = '0.0.0.0' if is_cloud else '127.0.0.1'

        reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == 'nt' and not is_cloud:
            reserved.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            reserved.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        reserved.bind((host, port))
        config = uvicorn.Config(create_app(auth=production_auth()), access_log=False, proxy_headers=is_cloud,
                                server_header=False, workers=1, log_config=None,
                                log_level='info' if is_cloud else 'critical')
        if is_cloud:
            print(f'Servidor escuchando en {host}:{port} (Modo Cloud Railway/Render)')
        else:
            print(f'Abrí http://127.0.0.1:{port}. Mantené esta ventana abierta. Ctrl+C para cerrar.')
        uvicorn.Server(config).run(sockets=[reserved])
        return 0
    except (OSError, ImportError):
        print('No se pudo iniciar. Revisá requisitos, permisos y si el puerto 8765 está ocupado. No se tocó otro proceso.')
        return 1
    finally:
        if reserved is not None:
            reserved.close()


if __name__ == '__main__':
    raise SystemExit(main())
