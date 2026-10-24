"""Pruebas del link firmado del certificado (Paso A). Sin red ni base: la base es un doble.

    python3 -m unittest discover -s tests -v
"""
import os
import re
import sys
import threading
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import certificado_firma as cf  # noqa: E402

SECRETO = "secreto-de-prueba"
ID = "orden-abc-123"
EXP = 1767225600000
# El MISMO vector está en BSL-PLATAFORMA2 (tests/certificado-empresa.test.js): si alguno de los
# dos lados cambia el formato de la firma, se rompe la prueba de ese lado.
FIRMA = "bd37a14484c8757dcd2508d6db9d5b56fc87a1115d1275aa2c912f5aa95f3b7d"
ANTES = EXP - 60_000  # un minuto antes de que venza


def leer(*partes):
    with open(os.path.join(RAIZ, *partes), encoding="utf-8") as f:
        return f.read()


class Firma(unittest.TestCase):
    def estado(self, exp, firma, wix_id=ID, ahora=ANTES, secreto=SECRETO):
        return cf.estado_firma(wix_id, exp, firma, secreto=secreto, ahora_ms=ahora)

    def test_vector_compartido_con_la_plataforma(self):
        self.assertEqual(cf._hmac(SECRETO, cf.PREFIJO, ID, EXP), FIRMA)
        self.assertEqual(self.estado(str(EXP), FIRMA), "valida")

    def test_link_sin_firma(self):
        self.assertEqual(self.estado(None, None), "sin_firma")
        self.assertEqual(self.estado("", ""), "sin_firma")

    def test_media_firma_es_invalida(self):
        self.assertEqual(self.estado(str(EXP), None), "invalida")
        self.assertEqual(self.estado(None, FIRMA), "invalida")

    def test_la_firma_esta_atada_al_id(self):
        self.assertEqual(self.estado(str(EXP), FIRMA, wix_id="otra-orden"), "invalida")

    def test_la_firma_esta_atada_al_vencimiento(self):
        self.assertEqual(self.estado(str(EXP + 1), FIRMA), "invalida")

    def test_vencida(self):
        self.assertEqual(self.estado(str(EXP), FIRMA, ahora=EXP + 1), "vencida")

    def test_una_firma_que_vence_demasiado_lejos_no_la_emitio_la_plataforma(self):
        lejos = EXP - cf.VIGENCIA_MAXIMA_MS - 1
        self.assertEqual(self.estado(str(EXP), FIRMA, ahora=lejos), "invalida")

    def test_otro_secreto(self):
        self.assertEqual(self.estado(str(EXP), FIRMA, secreto="otro"), "invalida")

    def test_malformada(self):
        for exp, firma in [("abc", FIRMA), (str(EXP), FIRMA.upper()), (str(EXP), FIRMA[:-1]),
                           (f" {EXP}", FIRMA), (str(EXP), FIRMA + "0"), (["1"], FIRMA)]:
            self.assertEqual(self.estado(exp, firma), "invalida", (exp, firma))

    def test_sin_secreto_en_este_servidor(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(cf.VARIABLE_SECRETO, None)
            self.assertEqual(cf.estado_firma(ID, str(EXP), FIRMA, ahora_ms=ANTES), "sin_secreto")
            self.assertEqual(cf.estado_firma(ID, None, None), "sin_firma")
            self.assertIsNone(cf.firmar(ID))
            self.assertEqual(cf.query_interna(ID), "")

    def test_el_secreto_sale_de_la_variable_de_entorno(self):
        with mock.patch.dict(os.environ, {cf.VARIABLE_SECRETO: SECRETO}):
            self.assertEqual(cf.estado_firma(ID, str(EXP), FIRMA, ahora_ms=ANTES), "valida")

    def test_firma_interna(self):
        exp, firma = cf.firmar(ID, secreto=SECRETO, ahora_ms=ANTES, interno=True)
        self.assertEqual(exp, ANTES + cf.VIGENCIA_INTERNA_MS)
        self.assertNotEqual(firma, cf._hmac(SECRETO, cf.PREFIJO, ID, exp))
        self.assertEqual(self.estado(str(exp), firma), "interna")
        self.assertEqual(self.estado(str(exp), firma, ahora=exp + 1), "vencida")
        self.assertEqual(self.estado(str(exp), firma, wix_id="otra-orden"), "invalida")

    def test_query_interna(self):
        with mock.patch.dict(os.environ, {cf.VARIABLE_SECRETO: SECRETO}):
            query = cf.query_interna(ID)
        m = re.fullmatch(r"exp=(\d+)&firma=([0-9a-f]{64})", query)
        self.assertIsNotNone(m, query)
        self.assertEqual(cf.estado_firma(ID, m.group(1), m.group(2), secreto=SECRETO), "interna")

    def test_parametros_para_reenviar_solo_pasan_digitos_y_hex(self):
        self.assertEqual(cf.parametros_para_reenviar({"exp": str(EXP), "firma": FIRMA}), (str(EXP), FIRMA))
        self.assertEqual(cf.parametros_para_reenviar({}), ("", ""))
        self.assertEqual(cf.parametros_para_reenviar(None), ("", ""))
        self.assertEqual(cf.parametros_para_reenviar({"exp": str(EXP), "firma": '"</script><script>x'}), ("", ""))
        self.assertEqual(cf.parametros_para_reenviar({"exp": "1;alert(1)", "firma": FIRMA}), ("", ""))


class DeDondeViene(unittest.TestCase):
    def test_agente(self):
        casos = {
            "WhatsApp/2.23.20.0 A": "whatsapp",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 HeadlessChrome/120.0 Safari/537.36": "puppeteer",
            "python-requests/2.31.0": "python",
            "Make/production": "make",
            "facebookexternalhit/1.1": "bot",
            "Mozilla/5.0 (compatible; Googlebot/2.1)": "bot",
            "Slackbot-LinkExpanding 1.0": "bot",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148": "navegador",
            "curl/8.4.0": "otro",
            "": "sin_agente",
            None: "sin_agente",
        }
        for ua, esperado in casos.items():
            self.assertEqual(cf.clasificar_agente(ua), esperado, ua)

    def test_origen_es_solo_el_host(self):
        self.assertEqual(cf.origen_de("https://bsl-plataforma.com/panel-empresas.html?id=abc"), "bsl-plataforma.com")
        self.assertEqual(cf.origen_de("https://usuario:clave@Medico-BSL.com:8443/x"), "medico-bsl.com:8443")
        self.assertEqual(cf.origen_de(""), "")
        self.assertEqual(cf.origen_de(None), "")

    def test_sitio(self):
        self.assertEqual(cf.sitio_de("same-origin"), "same-origin")
        self.assertEqual(cf.sitio_de("NONE"), "none")
        self.assertEqual(cf.sitio_de("cualquier-cosa"), "")
        self.assertEqual(cf.sitio_de(None), "")


class Req:
    """Lo mínimo de flask.request que usa el registro."""

    def __init__(self, endpoint, method="GET", view_args=None, args=None, headers=None, json=None):
        self.endpoint = endpoint
        self.method = method
        self.view_args = view_args
        self.args = args or {}
        self.headers = headers or {}
        self._json = json

    def get_json(self, silent=False):
        return self._json


NAVEGADOR = {
    "Referer": "https://bsl-plataforma.com/consulta-orden.html?ordenId=orden-abc-123",
    "Sec-Fetch-Site": "cross-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120",
}


class Registro(unittest.TestCase):
    def test_lo_que_no_es_una_puerta_del_certificado_no_se_cuenta(self):
        self.assertIsNone(cf.evento_de(Req("static", view_args={"filename": "x.png"})))
        self.assertIsNone(cf.evento_de(Req(None)))
        self.assertIsNone(cf.evento_de(Req("generar_certificado_desde_wix", method="OPTIONS",
                                           view_args={"wix_id": ID})))

    def test_link_sin_firma_se_cuenta_sin_datos_del_paciente(self):
        evento = cf.evento_de(Req("generar_certificado_desde_wix", view_args={"wix_id": ID}, headers=NAVEGADOR))
        self.assertEqual(evento, {
            "ruta": "loader", "firma": "sin_firma", "origen": "bsl-plataforma.com",
            "sitio": "cross-site", "agente": "navegador", "buscar": "id", "valor": ID,
        })

    def test_link_firmado(self):
        with mock.patch.dict(os.environ, {cf.VARIABLE_SECRETO: SECRETO}):
            with mock.patch.object(cf, "_ahora_ms", return_value=ANTES):
                evento = cf.evento_de(Req("api_generar_certificado_pdf", view_args={"wix_id": ID},
                                          args={"exp": str(EXP), "firma": FIRMA}))
        self.assertEqual((evento["ruta"], evento["firma"], evento["agente"]), ("pdf", "valida", "sin_agente"))

    def test_las_llamadas_internas_no_se_cuentan(self):
        with mock.patch.dict(os.environ, {cf.VARIABLE_SECRETO: SECRETO}):
            exp, firma = cf.firmar(ID, interno=True)
            req = Req("preview_certificado_html", view_args={"wix_id": ID}, args={"exp": str(exp), "firma": firma},
                      headers={"User-Agent": "HeadlessChrome/120"})
            self.assertIsNone(cf.evento_de(req))

    def test_envio_por_whatsapp(self):
        por_id = cf.evento_de(Req("enviar_certificado_whatsapp", method="POST", json={"historiaId": ID}))
        self.assertEqual((por_id["ruta"], por_id["firma"], por_id["buscar"]), ("enviar-whatsapp", "sin_firma", "id"))
        por_cedula = cf.evento_de(Req("enviar_certificado_whatsapp", method="POST", json={"numeroId": "123"}))
        self.assertEqual(por_cedula["buscar"], "cedula")
        self.assertIsNone(cf.evento_de(Req("enviar_certificado_whatsapp", method="POST", json={})))
        self.assertIsNone(cf.evento_de(Req("enviar_certificado_whatsapp", method="POST", json=["x"])))
        self.assertIsNone(cf.evento_de(Req("enviar_certificado_whatsapp", method="POST", json=None)))

    def test_registrar_nunca_lanza_ni_bloquea(self):
        class Rota:
            method = "GET"

            @property
            def endpoint(self):
                raise RuntimeError("request roto")

        with mock.patch("builtins.print"):
            self.assertIsNone(cf.registrar_apertura(Rota()))

    def test_registrar_encola_el_evento(self):
        with mock.patch.object(cf, "encolar") as encolar:
            self.assertIsNone(cf.registrar_apertura(Req("generar_certificado_desde_wix", view_args={"wix_id": ID})))
        encolar.assert_called_once()
        self.assertEqual(encolar.call_args[0][0]["ruta"], "loader")


class Cursor:
    def __init__(self, conexion):
        self.conexion = conexion

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        if self.conexion.falla:
            raise RuntimeError('relation "certificado_accesos" does not exist')
        self.conexion.ejecutadas.append((sql, dict(params)))


class Conexion:
    def __init__(self, falla=False):
        self.falla = falla
        self.ejecutadas = []
        self.commit_hecho = self.rollback_hecho = self.cerrada = False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commit_hecho = True

    def rollback(self):
        self.rollback_hecho = True

    def close(self):
        self.cerrada = True


class Escritura(unittest.TestCase):
    def evento(self, **cambios):
        e = {"ruta": "loader", "firma": "sin_firma", "origen": "", "sitio": "none", "agente": "navegador",
             "buscar": "id", "valor": ID}
        e.update(cambios)
        return e

    def test_un_lote_en_una_transaccion(self):
        con = Conexion()
        cf.escribir([self.evento(), self.evento(buscar="cedula", valor="123")], conectar_fn=lambda: con)
        self.assertEqual(len(con.ejecutadas), 2)
        self.assertEqual(con.ejecutadas[0][0], cf.SQL_POR_BUSQUEDA["id"])
        self.assertEqual(con.ejecutadas[1][0], cf.SQL_POR_BUSQUEDA["cedula"])
        self.assertTrue(con.commit_hecho and con.cerrada)

    def test_si_falla_deshace_cierra_y_avisa_al_hilo(self):
        con = Conexion(falla=True)
        with self.assertRaises(RuntimeError):
            cf.escribir([self.evento()], conectar_fn=lambda: con)
        self.assertTrue(con.rollback_hecho and con.cerrada)
        self.assertFalse(con.commit_hecho)

    def test_lote_vacio_no_conecta(self):
        cf.escribir([], conectar_fn=lambda: self.fail("no debía conectar"))

    def test_lo_que_se_guarda_no_tiene_datos_del_paciente(self):
        for sql in cf.SQL_POR_BUSQUEDA.values():
            columnas = re.search(r"INSERT INTO certificado_accesos \(([^)]*)\)", sql).group(1)
            self.assertEqual([c.strip() for c in columnas.split(",")],
                             ["dia", "ruta", "firma", "cod_empresa", "tenant_id", "origen", "sitio", "agente", "veces"])
            # El _id / la cédula solo aparecen en la búsqueda de la orden
            self.assertEqual(sql.count("%(valor)s"), 1)
            self.assertIn("'NUMERICO'", sql)

    def test_el_hilo_escribe_lo_encolado_sin_frenar_el_request(self):
        recibidos, listo = [], threading.Event()

        def escribir_falso(lote, conectar_fn=None):
            recibidos.extend(lote)
            if len(recibidos) >= 2:
                listo.set()

        with mock.patch.object(cf, "escribir", escribir_falso):
            cf.encolar(self.evento())
            cf.encolar(self.evento(ruta="pdf"))
            self.assertTrue(listo.wait(10), "el hilo no escribió")
        self.assertEqual(sorted(e["ruta"] for e in recibidos), ["loader", "pdf"])

    def test_si_la_cola_esta_llena_se_pierde_el_conteo_no_la_descarga(self):
        import queue
        llena = queue.Queue(maxsize=1)
        llena.put_nowait({})
        with mock.patch.object(cf, "_cola", llena):
            self.assertIsNone(cf.encolar(self.evento()))


class ConFlask(unittest.TestCase):
    """El enganche con un Flask de verdad: endpoint, view_args, cabeceras y el cuerpo intacto."""

    def setUp(self):
        try:
            import flask
        except ImportError:
            self.skipTest("flask no está instalado")
        app = flask.Flask(__name__)

        @app.before_request
        def _contar_apertura_certificado():
            return cf.registrar_apertura(flask.request)

        @app.route("/generar-certificado-desde-wix/<wix_id>", methods=["GET", "OPTIONS"])
        def generar_certificado_desde_wix(wix_id):
            return f"loader {wix_id}"

        @app.route("/enviar-certificado-whatsapp", methods=["POST"])
        def enviar_certificado_whatsapp():
            data = flask.request.get_json()  # la ruta real lo lee así, sin silent
            return flask.jsonify(recibido=data)

        @app.route("/otra")
        def otra():
            return "otra"

        self.cliente = app.test_client()
        self.encolados = []
        parche = mock.patch.object(cf, "encolar", self.encolados.append)
        parche.start()
        self.addCleanup(parche.stop)

    def test_la_descarga_sigue_igual_y_queda_contada(self):
        r = self.cliente.get(f"/generar-certificado-desde-wix/{ID}",
                             headers={"referer": "https://bsl-plataforma.com/x", "sec-fetch-site": "cross-site",
                                      "user-agent": "Mozilla/5.0"})
        self.assertEqual((r.status_code, r.get_data(as_text=True)), (200, f"loader {ID}"))
        self.assertEqual(len(self.encolados), 1)
        evento = self.encolados[0]
        self.assertEqual((evento["ruta"], evento["firma"], evento["origen"], evento["sitio"], evento["agente"]),
                         ("loader", "sin_firma", "bsl-plataforma.com", "cross-site", "navegador"))

    def test_el_cuerpo_del_envio_por_whatsapp_le_llega_entero_a_la_ruta(self):
        r = self.cliente.post("/enviar-certificado-whatsapp", json={"historiaId": ID})
        self.assertEqual(r.get_json(), {"recibido": {"historiaId": ID}})
        self.assertEqual(self.encolados[0]["buscar"], "id")

    def test_preflight_y_otras_rutas_no_se_cuentan(self):
        self.cliente.options(f"/generar-certificado-desde-wix/{ID}")
        self.assertEqual(self.cliente.get("/otra").get_data(as_text=True), "otra")
        self.assertEqual(self.encolados, [])


class Integracion(unittest.TestCase):
    """Lo que no se puede importar sin levantar la app (descargar_bsl.py), se revisa en el texto."""

    def setUp(self):
        self.app = leer("descargar_bsl.py")

    def test_cada_puerta_existe_en_la_app(self):
        for funcion in cf.PUERTAS:
            self.assertRegex(self.app, rf"\ndef {funcion}\(", funcion)

    def test_el_registro_esta_enganchado_antes_de_cada_request(self):
        self.assertRegex(self.app, r"@app\.before_request\ndef _contar_apertura_certificado\(\):\n"
                                   r"\s+return certificado_firma\.registrar_apertura\(request\)")

    def test_las_llamadas_a_si_mismo_van_con_firma_interna(self):
        self.assertEqual(self.app.count("certificado_firma.query_interna(wix_id)"), 2)

    def test_el_loader_pasa_la_firma_al_pdf(self):
        self.assertIn("certificado_firma.parametros_para_reenviar(request.args)", self.app)
        self.assertIn("firma_exp=firma_exp, firma=firma", self.app)

    def test_plantilla_del_loader(self):
        try:
            import jinja2
        except ImportError:
            self.skipTest("jinja2 no está instalado")
        entorno = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(RAIZ, "templates")),
                                     autoescape=True)
        plantilla = entorno.get_template("certificado_loader.html")
        firmada = plantilla.render(wix_id=ID, logo_url=None, firma_exp=str(EXP), firma=FIRMA)
        self.assertIn(f'const firmaExp = "{EXP}";', firmada)
        self.assertIn(f'const firma = "{FIRMA}";', firmada)
        self.assertIn("(firma ? `?exp=${firmaExp}&firma=${firma}` : '')", firmada)
        # Como la llaman hoy las otras rutas (sin firma): queda vacía y el PDF se pide como siempre
        sin_firma = plantilla.render(wix_id=ID, logo_url=None)
        self.assertIn('const firmaExp = "";', sin_firma)
        self.assertIn('const firma = "";', sin_firma)


if __name__ == "__main__":
    unittest.main()
