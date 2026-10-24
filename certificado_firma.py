"""
Link firmado del certificado — Paso A: aceptar la firma y contar quién abre el certificado.

POR QUÉ
    El certificado se abre con solo el _id de la orden (/generar-certificado-desde-wix/<_id>) y
    este servidor no mira la aprobación SST. Desde oct-2026 BSL-PLATAFORMA2 decide quién puede
    descargarlo (aprobación SST de SITEL, OMEGA y ZIMMER, permiso de descarga del usuario de
    empresa, la regla del paciente en consulta-orden) y, cuando lo permite, entrega el link
    FIRMADO. La firma es un HMAC-SHA256 con un secreto que comparten las dos apps (variable de
    entorno CERTIFICADO_FIRMA_SECRETO, NUNCA en el repo), atado al _id y con vencimiento corto:

        /generar-certificado-desde-wix/<_id>?exp=<milisegundos>&firma=<hex>
        firma = HMAC_SHA256(secreto, "certificado:<_id>|<exp>")

    Es el mismo formato de src/helpers/firma-interna.js de BSL-PLATAFORMA2. Las dos suites de
    pruebas verifican el mismo vector fijo, para que los dos lados no se desincronicen.

PASO A (este archivo)
    Un link sin firma sigue funcionando EXACTAMENTE igual que siempre. Lo único nuevo es que
    cada apertura de una puerta del certificado (firmada o no) se cuenta en la tabla
    certificado_accesos, que crea la migración 0008 de BSL-PLATAFORMA2: qué puerta, si traía
    firma, de qué empresa es la orden, de qué sitio vino (host del Referer y Sec-Fetch-Site) y
    qué cliente la abrió (navegador, WhatsApp, Puppeteer...). Son conteos por día: NUNCA se
    guarda el _id, nombres, cédulas ni la IP.

    Contar nunca puede tumbar una descarga: si la base falla o la tabla no existe todavía, se
    avisa una vez en el log y el certificado sale igual.

PASO B (otro PR, NO está aquí)
    Rechazar los links sin firma de SITEL, OMEGA y ZIMMER. Lo aprueba Daniel cuando el conteo
    muestre que ya nadie los usa.

LLAMADAS INTERNAS
    Este servidor se llama a sí mismo: el PDF abre el preview con Puppeteer y el envío por
    WhatsApp pide el PDF. Esas llamadas van con una firma "interna" (otro prefijo), que se
    reconoce y no se cuenta: son consecuencia de una apertura que ya se contó.

Solo biblioteca estándar (psycopg2 se importa al escribir), para probarlo sin levantar la app:
    python3 -m unittest discover -s tests
"""

import hashlib
import hmac
import os
import queue
import re
import threading
import time
from urllib.parse import urlparse

VARIABLE_SECRETO = "CERTIFICADO_FIRMA_SECRETO"

PREFIJO = "certificado"                    # lo firma BSL-PLATAFORMA2
PREFIJO_INTERNO = "certificado-interno"    # lo firma este servidor para llamarse a sí mismo

# BSL-PLATAFORMA2 firma por 10 minutos. Se acepta hasta 15 por diferencias de reloj; una firma
# que vence más lejos no la pudo emitir la plataforma y se cuenta como inválida.
VIGENCIA_MAXIMA_MS = 15 * 60 * 1000
# La firma interna dura lo que tarda un PDF con holgura (el envío por WhatsApp espera 180 s).
VIGENCIA_INTERNA_MS = 5 * 60 * 1000

_RE_FIRMA = re.compile(r"^[0-9a-f]{64}$")
_RE_EXP = re.compile(r"^[0-9]{1,16}$")

# Puertas del certificado: endpoint de Flask (nombre de la función) → nombre corto en el conteo.
# Si se renombra una de esas funciones, tests/test_certificado_firma.py lo detecta.
PUERTAS = {
    "generar_certificado_desde_wix": "loader",
    "api_generar_certificado_pdf": "pdf",
    "preview_certificado_html": "preview-html",
    "generar_certificado_desde_wix_puppeteer": "loader-puppeteer",
    "generar_certificado_alegra": "alegra-loader",
    "api_generar_certificado_alegra": "alegra-pdf",
    "preview_certificado_alegra": "alegra-preview",
    "generar_certificado_v2": "v2-loader",
    "api_generar_certificado_pdf_v2": "v2-pdf",
    "preview_certificado_v2": "v2-preview",
    "generar_certificado_v2_drive": "v2-drive-loader",
    "api_generar_certificado_pdf_v2_drive": "v2-drive-pdf",
    "test_certificado_postgres": "test-postgres",
    "enviar_certificado_whatsapp": "enviar-whatsapp",
}

ESTADOS = ("valida", "sin_firma", "vencida", "invalida", "sin_secreto", "interna")


# ----------------------------------------------------------------------------------------------
# Firma
# ----------------------------------------------------------------------------------------------

def _secreto():
    return os.environ.get(VARIABLE_SECRETO) or None


def _ahora_ms():
    return int(time.time() * 1000)


def _hmac(secreto, prefijo, wix_id, exp):
    mensaje = f"{prefijo}:{wix_id}|{exp}".encode("utf-8")
    return hmac.new(secreto.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def firmar(wix_id, secreto=None, ahora_ms=None, interno=False, vigencia_ms=VIGENCIA_INTERNA_MS):
    """(exp, firma) para ese _id, o None si este servidor no tiene el secreto."""
    secreto = _secreto() if secreto is None else secreto
    if not secreto:
        return None
    exp = (_ahora_ms() if ahora_ms is None else ahora_ms) + vigencia_ms
    return exp, _hmac(secreto, PREFIJO_INTERNO if interno else PREFIJO, str(wix_id), exp)


def query_interna(wix_id):
    """'exp=…&firma=…' para que este servidor se llame a sí mismo sin contarse ('' sin secreto)."""
    firmado = firmar(wix_id, interno=True)
    return f"exp={firmado[0]}&firma={firmado[1]}" if firmado else ""


def estado_firma(wix_id, exp, firma, secreto=None, ahora_ms=None):
    """Clasifica la firma que trae un link. Uno de ESTADOS; nunca lanza."""
    if not exp and not firma:
        return "sin_firma"
    secreto = _secreto() if secreto is None else secreto
    if not secreto:
        return "sin_secreto"
    if not isinstance(exp, str) or not isinstance(firma, str) \
            or not _RE_EXP.match(exp) or not _RE_FIRMA.match(firma):
        return "invalida"
    vence = int(exp)
    ahora = _ahora_ms() if ahora_ms is None else ahora_ms
    wid = str(wix_id)
    if hmac.compare_digest(_hmac(secreto, PREFIJO_INTERNO, wid, vence), firma):
        if vence < ahora:
            return "vencida"
        return "interna" if vence <= ahora + VIGENCIA_MAXIMA_MS else "invalida"
    if not hmac.compare_digest(_hmac(secreto, PREFIJO, wid, vence), firma):
        return "invalida"
    if vence < ahora:
        return "vencida"
    if vence > ahora + VIGENCIA_MAXIMA_MS:
        return "invalida"
    return "valida"


def parametros_para_reenviar(args):
    """(exp, firma) del link si tienen la forma correcta, para que el loader los pase al PDF.

    Solo dígitos y hexadecimal: esos valores se escriben dentro de un <script> de la página.
    """
    exp = (args.get("exp") or "") if args else ""
    firma = (args.get("firma") or "") if args else ""
    if _RE_EXP.match(exp) and _RE_FIRMA.match(firma):
        return exp, firma
    return "", ""


# ----------------------------------------------------------------------------------------------
# De dónde viene (sin datos personales: solo hosts y familias de cliente)
# ----------------------------------------------------------------------------------------------

_AGENTES = (
    ("whatsapp", re.compile(r"whatsapp", re.I)),
    ("puppeteer", re.compile(r"headlesschrome", re.I)),
    ("python", re.compile(r"python-requests|python-urllib|aiohttp|httpx", re.I)),
    ("make", re.compile(r"\bmake/|integromat", re.I)),
    ("bot", re.compile(r"bot\b|crawler|spider|facebookexternalhit|preview", re.I)),
    ("navegador", re.compile(r"mozilla/", re.I)),
)

_SITIOS = {"none", "same-origin", "same-site", "cross-site"}


def clasificar_agente(user_agent):
    ua = (user_agent or "").strip()
    if not ua:
        return "sin_agente"
    for nombre, patron in _AGENTES:
        if patron.search(ua):
            return nombre
    return "otro"


def origen_de(referer):
    """Solo el host del Referer (sin ruta, sin query, sin usuario): '' si no vino."""
    if not referer:
        return ""
    try:
        host = urlparse(referer).netloc.rsplit("@", 1)[-1].lower()
    except Exception:
        return "?"
    return host[:120]


def sitio_de(valor):
    v = (valor or "").strip().lower()
    return v if v in _SITIOS else ""


# ----------------------------------------------------------------------------------------------
# Registro (before_request): cuenta, nunca bloquea
# ----------------------------------------------------------------------------------------------

def evento_de(req):
    """El conteo que corresponde a este request, o None si no es una puerta del certificado."""
    if req.method == "OPTIONS":
        return None
    ruta = PUERTAS.get(req.endpoint or "")
    if not ruta:
        return None
    if ruta == "enviar-whatsapp":
        cuerpo = req.get_json(silent=True)
        cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
        if cuerpo.get("historiaId"):
            buscar, valor = "id", str(cuerpo["historiaId"])
        elif cuerpo.get("numeroId"):
            buscar, valor = "cedula", str(cuerpo["numeroId"])
        else:
            return None
        estado = "sin_firma"
    else:
        wix_id = (req.view_args or {}).get("wix_id")
        if not wix_id:
            return None
        buscar, valor = "id", str(wix_id)
        estado = estado_firma(wix_id, req.args.get("exp"), req.args.get("firma"))
        if estado == "interna":
            return None
    cabeceras = req.headers
    return {
        "ruta": ruta,
        "firma": estado,
        "origen": origen_de(cabeceras.get("Referer")),
        "sitio": sitio_de(cabeceras.get("Sec-Fetch-Site")),
        "agente": clasificar_agente(cabeceras.get("User-Agent")),
        # Solo para buscar la empresa de la orden en la base; NO se guarda.
        "buscar": buscar,
        "valor": valor[:200],
    }


def registrar_apertura(req):
    """Para @app.before_request. Devuelve None siempre: el request sigue como si nada."""
    try:
        evento = evento_de(req)
        if evento:
            encolar(evento)
    except Exception as error:  # contar nunca puede tumbar una descarga
        _avisar_una_vez("registrar", error)
    return None


# ----------------------------------------------------------------------------------------------
# Escritura en la base, fuera del request: una cola y un solo hilo que junta lo de 2 segundos
# ----------------------------------------------------------------------------------------------

_cola = queue.Queue(maxsize=2000)
_hilo = None
_candado = threading.Lock()
_avisados = set()

# Upsert del conteo del día. La empresa se saca de la orden y se guarda en mayúsculas; un código
# de 6 o más dígitos (puede ser un documento) se guarda como NUMERICO. El _id o la cédula solo
# sirven para encontrar la orden: no van a ninguna columna.
def _insertar(buscar_orden):
    return (
        "INSERT INTO certificado_accesos "
        "(dia, ruta, firma, cod_empresa, tenant_id, origen, sitio, agente, veces) "
        "SELECT (now() AT TIME ZONE 'America/Bogota')::date, %(ruta)s, %(firma)s, "
        "COALESCE(CASE WHEN h.\"codEmpresa\" ~ '^[0-9]{6,}$' THEN 'NUMERICO' "
        "ELSE left(upper(trim(h.\"codEmpresa\")), 100) END, ''), "
        "COALESCE(h.tenant_id, ''), %(origen)s, %(sitio)s, %(agente)s, 1 "
        "FROM (SELECT 1) AS uno "
        "LEFT JOIN LATERAL (" + buscar_orden + ") AS h ON true "
        "ON CONFLICT (dia, ruta, firma, cod_empresa, tenant_id, origen, sitio, agente) "
        "DO UPDATE SET veces = certificado_accesos.veces + 1, ultima = now()"
    )


SQL_POR_BUSQUEDA = {
    "id": _insertar('SELECT "codEmpresa", tenant_id FROM "HistoriaClinica" '
                    'WHERE "_id" = %(valor)s LIMIT 1'),
    "cedula": _insertar('SELECT "codEmpresa", tenant_id FROM "HistoriaClinica" '
                        'WHERE "numeroId" = %(valor)s ORDER BY "_createdDate" DESC LIMIT 1'),
}


def _avisar_una_vez(clave, error):
    nombre = f"{clave}:{type(error).__name__}"
    if nombre in _avisados:
        return
    _avisados.add(nombre)
    print(f"⚠️ [conteo-certificados] {clave}: {type(error).__name__}: {error} "
          f"(el certificado sale igual; este aviso no se repite)")


def conectar():
    """Conexión corta a la misma base que usa la app (mismas variables)."""
    import psycopg2
    clave = os.getenv("POSTGRES_PASSWORD")
    if not clave:
        raise RuntimeError("POSTGRES_PASSWORD no configurada")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
        port=int(os.getenv("POSTGRES_PORT", "25060")),
        user=os.getenv("POSTGRES_USER", "doadmin"),
        password=clave,
        database=os.getenv("POSTGRES_DB", "defaultdb"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        connect_timeout=5,
        application_name="bsl-utilidades-conteo-certificados",
        options="-c statement_timeout=5000",
    )


def escribir(lote, conectar_fn=None):
    """Escribe un lote de conteos en una transacción. Lanza si falla (lo atrapa el hilo)."""
    if not lote:
        return
    conexion = (conectar_fn or conectar)()
    try:
        with conexion.cursor() as cursor:
            for evento in lote:
                cursor.execute(SQL_POR_BUSQUEDA[evento["buscar"]], evento)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def _juntar_lote(espera_s=2.0, maximo=200):
    lote = [_cola.get()]
    fin = time.monotonic() + espera_s
    while len(lote) < maximo:
        restante = fin - time.monotonic()
        if restante <= 0:
            break
        try:
            lote.append(_cola.get(timeout=restante))
        except queue.Empty:
            break
    return lote


def _trabajar():
    while True:
        lote = _juntar_lote()
        try:
            escribir(lote)
        except Exception as error:
            _avisar_una_vez("escribir", error)


def encolar(evento):
    """Deja el conteo en la cola (si está llena se pierde el conteo, nunca la descarga)."""
    global _hilo
    try:
        _cola.put_nowait(evento)
    except queue.Full:
        return
    if _hilo is None or not _hilo.is_alive():
        with _candado:
            if _hilo is None or not _hilo.is_alive():
                _hilo = threading.Thread(target=_trabajar, name="conteo-certificados", daemon=True)
                _hilo.start()
