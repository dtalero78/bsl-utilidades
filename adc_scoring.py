"""
Modulo de calificacion del Perfil Psicologico ADC.

Porta la logica de calificacion del archivo MediData (ADC - RESULTADOS)
a Python. Incluye las tres escalas: Ansiedad, Congruencia y Depresion,
con sus baremos, textos interpretativos y matriz de congruencia.
"""

# ============================================================
# CONVERSION DE RESPUESTAS A PUNTAJES
# ============================================================

SCORE_DA = {
    "De acuerdo": 3,
    "Medianamente de acuerdo": 2,
    "Medianamente en desacuerdo": 1,
    "En desacuerdo": 0,
}

SCORE_DE = {
    "De acuerdo": 0,
    "Medianamente de acuerdo": 1,
    "Medianamente en desacuerdo": 2,
    "En desacuerdo": 3,
}


def puntuar_respuesta(respuesta_texto, direccion):
    if not respuesta_texto:
        return 0
    tabla = SCORE_DA if direccion == "DA" else SCORE_DE
    return tabla.get(respuesta_texto.strip(), 0)


# ============================================================
# DEFINICION DE ITEMS POR ESCALA
# ============================================================

ANSIEDAD_ITEMS = {
    "Afectivo": [("an18", "DE"), ("an19", "DA"), ("an20", "DA"), ("an31", "DE"), ("an35", "DE")],
    "Cognitiva": [("an03", "DA"), ("an04", "DE"), ("an05", "DA"), ("an22", "DA"), ("an23", "DE")],
    "Conductual": [("an11", "DA"), ("an14", "DA"), ("an36", "DE"), ("an38", "DA"), ("an39", "DA")],
    "Fisiologica": [("an07", "DA"), ("an09", "DA"), ("an26", "DE"), ("an27", "DA"), ("an30", "DE")],
}

DEPRESION_ITEMS = {
    "Sobre Futuro": [("de08", "DE"), ("de12", "DA"), ("de13", "DE"), ("de35", "DE"), ("de37", "DE"), ("de38", "DA"), ("de40", "DE")],
    "Sobre Mundo": [("de14", "DA"), ("de15", "DA"), ("de16", "DA"), ("de20", "DA"), ("de29", "DA"), ("de32", "DA"), ("de33", "DA")],
    "Sobre Ti Mismo": [("de03", "DA"), ("de04", "DE"), ("de05", "DA"), ("de06", "DA"), ("de07", "DA"), ("de21", "DE"), ("de27", "DE")],
}

CONGRUENCIA_ITEMS = {
    "familia_valoracion": [("cofv01", "DA"), ("cofv02", "DE"), ("cofv03", "DA")],
    "familia_conducta": [("cofc06", "DE"), ("cofc08", "DE"), ("cofc10", "DE")],
    "relacion_valoracion": [("corv11", "DA"), ("corv12", "DE"), ("corv15", "DA")],
    "relacion_conducta": [("corc16", "DE"), ("corc17", "DE"), ("corc18", "DE")],
    "autocuidado_valoracion": [("coav21", "DA"), ("coav24", "DA"), ("coav25", "DA")],
    "autocuidado_conducta": [("coac26", "DA"), ("coac27", "DE"), ("coac29", "DA")],
    "ocupacional_valoracion": [("coov32", "DA"), ("coov34", "DA"), ("coov35", "DE")],
    "ocupacional_conducta": [("cooc37", "DA"), ("cooc39", "DE"), ("cooc40", "DA")],
}

# ============================================================
# BAREMOS - ANSIEDAD
# ============================================================

BAREMO_ANSIEDAD_AFECTIVO = {
    15: 27, 14: 25, 13: 24, 12: 23, 11: 22, 10: 20,
    9: 19, 8: 18, 7: 17, 6: 15, 5: 14, 4: 13,
    3: 12, 2: 10, 1: 9, 0: 8,
}

BAREMO_ANSIEDAD_COGNITIVA = {
    15: 22, 14: 21, 13: 20, 12: 19, 11: 18, 10: 17,
    9: 16, 8: 15, 7: 14, 6: 13, 5: 12, 4: 11,
    3: 10, 2: 9, 1: 8, 0: 7,
}

BAREMO_ANSIEDAD_CONDUCTUAL = {
    15: 25, 14: 24, 13: 22, 12: 21, 11: 19, 10: 18,
    9: 16, 8: 15, 7: 13, 6: 12, 5: 11, 4: 9,
    3: 8, 2: 6, 1: 5, 0: 3,
}

BAREMO_ANSIEDAD_FISIOLOGICA = {
    15: 27, 14: 26, 13: 24, 12: 23, 11: 22, 10: 20,
    9: 19, 8: 18, 7: 17, 6: 15, 5: 14, 4: 13,
    3: 11, 2: 10, 1: 9, 0: 8,
}

BAREMO_ANSIEDAD_GENERAL = {
    49: 24, 48: 23, 47: 23, 46: 22, 45: 22, 44: 22,
    43: 21, 42: 21, 41: 21, 40: 20, 39: 20, 38: 20,
    37: 19, 36: 19, 35: 19, 34: 18, 33: 18, 32: 17,
    31: 17, 30: 17, 29: 16, 28: 16, 27: 16, 26: 15,
    25: 15, 24: 15, 23: 14, 22: 14, 21: 13, 20: 13,
    19: 13, 18: 12, 17: 12, 16: 12, 15: 11, 14: 11,
    13: 11, 12: 10, 11: 10, 10: 9, 9: 9, 8: 9,
    7: 8, 6: 8, 5: 8, 4: 7, 3: 7, 2: 7,
    1: 6, 0: 6,
}

BAREMOS_ANSIEDAD = {
    "Afectivo": BAREMO_ANSIEDAD_AFECTIVO,
    "Cognitiva": BAREMO_ANSIEDAD_COGNITIVA,
    "Conductual": BAREMO_ANSIEDAD_CONDUCTUAL,
    "Fisiologica": BAREMO_ANSIEDAD_FISIOLOGICA,
}

# ============================================================
# BAREMOS - DEPRESION
# ============================================================

BAREMO_DEPRESION_FUTURO = {
    21: 35, 20: 34, 19: 32, 18: 31, 17: 30, 16: 28,
    15: 27, 14: 26, 13: 25, 12: 23, 11: 22, 10: 21,
    9: 20, 8: 18, 7: 17, 6: 16, 5: 15, 4: 13,
    3: 12, 2: 11, 1: 10, 0: 8,
}

BAREMO_DEPRESION_MUNDO = {
    21: 28, 20: 27, 19: 26, 18: 25, 17: 24, 16: 23,
    15: 22, 14: 21, 13: 20, 12: 19, 11: 18, 10: 18,
    9: 17, 8: 16, 7: 15, 6: 14, 5: 13, 4: 12,
    3: 11, 2: 10, 1: 9, 0: 8,
}

BAREMO_DEPRESION_TI_MISMO = {
    21: 36, 20: 35, 19: 33, 18: 32, 17: 31, 16: 29,
    15: 28, 14: 27, 13: 25, 12: 24, 11: 23, 10: 21,
    9: 20, 8: 19, 7: 18, 6: 16, 5: 15, 4: 14,
    3: 12, 2: 11, 1: 10, 0: 8,
}

BAREMO_DEPRESION_GENERAL = {
    49: 29, 48: 28, 47: 28, 46: 27, 45: 27, 44: 27,
    43: 26, 42: 26, 41: 25, 40: 25, 39: 25, 38: 24,
    37: 24, 36: 23, 35: 23, 34: 22, 33: 22, 32: 22,
    31: 21, 30: 21, 29: 20, 28: 20, 27: 19, 26: 19,
    25: 19, 24: 18, 23: 18, 22: 17, 21: 17, 20: 16,
    19: 16, 18: 16, 17: 15, 16: 15, 15: 14, 14: 14,
    13: 13, 12: 13, 11: 13, 10: 12, 9: 12, 8: 11,
    7: 11, 6: 11, 5: 10, 4: 10, 3: 9, 2: 9,
    1: 8, 0: 8,
}

BAREMOS_DEPRESION = {
    "Sobre Futuro": BAREMO_DEPRESION_FUTURO,
    "Sobre Mundo": BAREMO_DEPRESION_MUNDO,
    "Sobre Ti Mismo": BAREMO_DEPRESION_TI_MISMO,
}

# ============================================================
# BAREMOS - CONGRUENCIA
# ============================================================

BAREMO_FAMILIA_VALORACION = {
    9: 19, 8: 17, 7: 14, 6: 11, 5: 9, 4: 6, 3: 4, 2: 1, 1: -2, 0: -4,
}
BAREMO_FAMILIA_CONDUCTA = {
    9: 17, 8: 16, 7: 14, 6: 13, 5: 11, 4: 10, 3: 8, 2: 7, 1: 5, 0: 4,
}
BAREMO_RELACION_VALORACION = {
    9: 19, 8: 17, 7: 15, 6: 12, 5: 10, 4: 8, 3: 5, 2: 3, 1: 1, 0: -2,
}
BAREMO_RELACION_CONDUCTA = {
    9: 18, 8: 16, 7: 15, 6: 13, 5: 12, 4: 10, 3: 8, 2: 7, 1: 5, 0: 3,
}
BAREMO_AUTOCUIDADO_VALORACION = {
    9: 22, 8: 18, 7: 15, 6: 12, 5: 8, 4: 5, 3: 2, 2: -2, 1: -5, 0: -8,
}
BAREMO_AUTOCUIDADO_CONDUCTA = {
    9: 18, 8: 17, 7: 15, 6: 13, 5: 11, 4: 10, 3: 8, 2: 6, 1: 4, 0: 3,
}
BAREMO_OCUPACIONAL_VALORACION = {
    9: 20, 8: 17, 7: 15, 6: 12, 5: 10, 4: 7, 3: 5, 2: 2, 1: 0, 0: -3,
}
BAREMO_OCUPACIONAL_CONDUCTA = {
    9: 19, 8: 17, 7: 15, 6: 12, 5: 10, 4: 8, 3: 6, 2: 4, 1: 1, 0: -1,
}

BAREMOS_CONGRUENCIA = {
    "familia_valoracion": BAREMO_FAMILIA_VALORACION,
    "familia_conducta": BAREMO_FAMILIA_CONDUCTA,
    "relacion_valoracion": BAREMO_RELACION_VALORACION,
    "relacion_conducta": BAREMO_RELACION_CONDUCTA,
    "autocuidado_valoracion": BAREMO_AUTOCUIDADO_VALORACION,
    "autocuidado_conducta": BAREMO_AUTOCUIDADO_CONDUCTA,
    "ocupacional_valoracion": BAREMO_OCUPACIONAL_VALORACION,
    "ocupacional_conducta": BAREMO_OCUPACIONAL_CONDUCTA,
}

# ============================================================
# TEXTOS INTERPRETATIVOS - ANSIEDAD
# ============================================================

INTERP_ANSIEDAD_AFECTIVO = [
    (4, "Tu vivencia afectiva es de tranquilidad y relajacion ante los eventos, incluso aquellos que deberian afectarte por las implicaciones, riesgos y peligros que conllevan. Pareces no tener miedo ni preocupaciones en situaciones que lo ameritan."),
    (7, "Te sientes tranquilo y no pareces tener preocupaciones o temores para enfrentarte al entorno o a la perspectiva de lo que pueda ocurrir en el futuro. No te parece alterar ante las situaciones y la mayor parte del tiempo te muestras calmado y seguro."),
    (10, "Ante situaciones dificiles, puedes reaccionar con preocupacion, pero eres capaz de gestionar tus emociones para mantener el control y la tranquilidad de forma tal que puedes ajustar tus estados emocionales a la urgencia o dificultad de las circunstancias, entendiendo que son solucionables."),
    (13, "Es posible que ante la incertidumbre o situaciones de presion se genere en ti una cierta sensacion de tension y temores anticipatorios ante lo desconocido y la incertidumbre que ello genera. Sin embargo, logras enfrentarlos y manejar las circunstancias de manera efectiva."),
    (16, "En tu caso, la sensacion de temor, miedo, intranquilidad, irritabilidad e inquietud se presenta de manera recurrente ante lo inesperado o situaciones que evaluas como potencialmente peligrosas, anticipando con tus respuestas afectivas los posibles fracasos y riesgos que piensas que se produciran."),
    (99, "En este caso, la vivencia cotidiana esta acompanada de temores ante peligros percibidos como inminentes, con lo cual la persona esta constantemente intranquila, temorosa e irritable sin poder ejercer control sobre las sensaciones de incomodidad ante las cuales se siente impotente."),
]

INTERP_ANSIEDAD_COGNITIVA = [
    (4, "No hay presencia de preocupaciones y tu pensamiento es rapido y preciso. Tienes ideas que te ayudan a comprender y proyectar tus objetivos. Tu funcionamiento mental es productivo, aunque en ocasiones tus procesos pueden ser rapidos e impulsivos, lo cual puede hacerte sentir disperso."),
    (7, "Tus procesos de generacion de ideas, atencion y memoria estan conservados y los enfocas en la produccion de proyectos y planes. Pareces necesitar de planeacion y anticipacion ya que te enfocas en las condiciones presentes, sin tener en cuenta posibles desenlaces a futuro."),
    (10, "Analizas de manera objetiva y precisa las situaciones y tus procesos de atencion y concentracion te permiten mantenerte en las ideas, planes y propositos, reconociendo los aspectos positivos y negativos de los mismos. Eres capaz de anticipar las dificultades y planear la forma de sortearlas adecuadamente."),
    (13, "Puedes hacer un analisis de la situacion, generar ideas y propuestas para hacer frente a la misma. Eventualmente llegas a pensar en que es posible que tus recursos (capacidades) no son suficientes para actuar de forma que aporte a las circunstancias a las que te enfrentas."),
    (16, "Ante las presiones, puedes responder con dificultad para organizar las ideas y pueden existir dificultades para pensar de forma objetiva. Puede darse una percepcion de bloqueo que hace pensar en un procesamiento lento de la informacion."),
    (99, "Los pensamientos parecen estar dirigidos a anticipar situaciones catastroficas que se puedan presentar, y con ello, se altera tu procesamiento de informacion, ya que tu atencion, concentracion y memoria estan focalizadas en las preocupaciones y temores ante lo que puede suceder."),
]

INTERP_ANSIEDAD_CONDUCTUAL = [
    (4, "Sueles tener iniciativas que pueden describirse como un tanto impulsivas y poco planeadas. Incluso pones en practica planes sin tomar en cuenta los riesgos que pueden ser inherentes a ellos. Tu conducta se caracteriza por la inmediatez y falta de planeacion."),
    (7, "Enfrentas los peligros sin preocuparte demasiado por ellos. La evaluacion que haces de tu entorno es positiva y, en ocasiones, puedes pasar por alto los riesgos implicitos en una situacion. Tu perspectiva es confiada y desprejuiciada, y asumes tener el control."),
    (10, "Puedes evaluar adecuadamente las situaciones y actuar en concordancia con lo esperado y requerido. Toleras la novedad y la incomodidad en diversas circunstancias y actuas de forma tal que mantienes el control de la situacion y la tranquilidad para tomar decisiones."),
    (13, "Es posible que ante exigencias inesperadas generes respuestas de evitacion o postergacion para asegurarte de actuar de manera adecuada. Sin embargo, logras gestionar adecuadamente tus conductas para enfrentarte a tus propias incertidumbres y actuar de manera adecuada acorde con lo esperado."),
    (16, "Cuando te enfrentas a situaciones inesperadas o elevadas exigencias, respondes con evitacion o postergacion de la situacion para tratar de mantenerse en lo conocido, evitando la incertidumbre de situaciones nuevas."),
    (99, "Tu comportamiento esta dirigido a evitar peligros, evadir riesgos y responder ante lo inesperado tratando de protegerte del peligro. Por ello, sueles estar aislado, con una percepcion de estar debilitado y fisicamente paralizado ante una situacion que te supera y te impide movilizar tus recursos."),
]

INTERP_ANSIEDAD_FISIOLOGICA = [
    (4, "Tu cuerpo suele estar relajado, con poca o ninguna responsividad ante situaciones que usualmente generan preocupacion o respuestas de tension y alerta en otras personas. Los sistemas corporales parecen no tener respuesta inmediata ante las preocupaciones y situaciones de exigencia."),
    (7, "El funcionamiento de los diferentes sistemas corporales (digestivo, nervioso, etc.) es adecuado, aunque tus respuestas ante las situaciones de posible tension, amenaza y exigencia son de baja intensidad, con lo cual se mantiene un estado de calma y relajacion casi constante."),
    (10, "Tus respuestas frente a las situaciones que evaluas como dificiles y conflictivas son apropiadas. Generas un adecuado nivel de alerta cuando la situacion efectivamente genera tension, sin embargo, estos son estados que puedes gestionar sin que te generen malestar fisico y alteraciones."),
    (13, "Frente a situaciones exigentes, generas un estado de alerta que puede generar manifestaciones de tension (por ejemplo, temblor o sudoracion) manejables, que suelen desaparecer cuando te aseguras de que cuentas con las posibilidades de enfrentar los problemas o cuando se resuelve la fuente de preocupacion."),
    (16, "En respuesta a las situaciones en las que percibes no tener las habilidades para dar respuesta a las exigencias, es frecuente que aparezcan temblores, dolores, tension muscular y alteracion de los ritmos de sueno, apetito y otras actividades de la vida cotidiana."),
    (99, "Son casi constantes tus respuestas de tension muscular, dolores inespecificos, sudoracion, taquicardia, insomnio y sensaciones variables de adormecimiento o paralisis de extremidades, las cuales son respuesta ante una realidad percibida como amenazante."),
]

INTERP_ANSIEDAD_GENERAL = [
    (4, "No se presentan indicadores de ansiedad en ninguna de las areas de funcionamiento y relacionamiento. Parece existir una falta de respuesta ante situaciones que requieren algun tipo de alerta para manejarlas adecuadamente. Lo anterior puede ser un indicador de desinteres o superficialidad ante ellas."),
    (7, "Existen pocas preocupaciones y escasa respuesta de alerta ante situaciones que podrian ameritarla. Hay una marcada tendencia de tu parte a conservar la calma, mantenerte tranquilo y relajado, con lo cual tus preocupaciones frente al entorno son minimas, pudiendo desatender temas que lo merecen."),
    (10, "Ante las situaciones dificiles, generas respuestas con un adecuado nivel de ansiedad que te permite gestionar tu actuar en correspondencia con las circunstancias, sin perder el control y manteniendo una relativa calma ante las dificultades. Reconoces lo que es motivo de preocupacion y lo abordas para buscar soluciones."),
    (13, "Posees recursos y estrategias para enfrentarte a situaciones nuevas o inesperadas, pero es posible que presentes tension, temor y respuestas de incomodidad ante ellas. Sin embargo, logras manejarlas con exito, recuperar la calma y la seguridad de tener el control cuando superas los problemas u obstaculos."),
    (16, "La presencia de ansiedad es frecuente, y por ello la realidad se vive como una fuente de preocupaciones y temores que te llevan a desarrollar respuestas de tension fisica y emocional. A nivel afectivo, predomina un sentimiento de aprension y miedo ante peligros anticipatorios e irreales."),
    (99, "La ansiedad alta y generalizada dificulta la adaptacion y las relaciones. Te centras en protegerte de peligros inminentes que anticipas, lo cual puede generar sintomas fisicos y psicologicos que alteran tu cotidianidad y son fuente de elevado sufrimiento, malestar e incomodidad."),
]

INTERP_ANSIEDAD = {
    "Afectivo": INTERP_ANSIEDAD_AFECTIVO,
    "Cognitiva": INTERP_ANSIEDAD_COGNITIVA,
    "Conductual": INTERP_ANSIEDAD_CONDUCTUAL,
    "Fisiologica": INTERP_ANSIEDAD_FISIOLOGICA,
}

# ============================================================
# TEXTOS INTERPRETATIVOS - DEPRESION
# ============================================================

INTERP_DEPRESION_FUTURO = [
    (4, "Percibes tu futuro como prometedor, incluso en ocasiones de forma idealizada asumiendo que todo puede ser logrado. Tienes una alta motivacion que te hace pensar que puedes alcanzar las metas que te propongas sin mayores esfuerzos."),
    (7, "Ves tu futuro con esperanza y como una posibilidad de alcanzar lo que te propones, percibes que alcanzaras metas y objetivos con relativa facilidad y te sientes motivado a actuar para llevar a cabo tus proyectos ya que tienes seguridad frente a tus logros."),
    (10, "Reconoces que el futuro implica retos, por ello entiendes que debes abordarlo con tus altas y tus bajas. Sabes que puedes construir resultados a partir de tu motivacion y esfuerzo para lograr lo que te has propuesto. Tu vision sobre el porvenir es realista y equilibrada."),
    (13, "Cuando piensas en planes y proyectos a desarrollar eres entusiasta frente a las posibilidades de alcanzar logros y tener exito en ellos. Sientes que debes esforzarte posiblemente mas que otras personas, pero conservas un relativo optimismo frente a los resultados."),
    (16, "Tus expectativas a futuro son limitadas, por cuanto anticipas dificultades importantes, exigencias muy elevadas y resultados negativos. Sientes que por mas que te esfuerces no vas a alcanzar lo que se espera de ti, por lo que evitas generar planes para el porvenir."),
    (99, "Tu percepcion de futuro es muy desalentadora y negativa. Frente al porvenir no ves posibilidades, tu perspectiva es pesimista y por ello no ves salidas ni te proyectas a futuro, sientes que no lo tendras y puedes pensar que no mereces hacer planes ya que no eres capaz de cambiar nada o de aportar."),
]

INTERP_DEPRESION_MUNDO = [
    (4, "Estableces relaciones de confianza y desprevenidas con tu entorno, disfrutas de las actividades compartidas, le das importancia a toda nueva experiencia y oportunidad de tener contacto con los otros, valorando a los demas de forma inmediata."),
    (7, "Disfrutas la compania y las relaciones interpersonales, te permites vivir nuevas experiencias con optimismo y apertura. Evaluas tu entorno y sientes que siempre existen oportunidades de alcanzar tus logros y metas sin mayores dificultades."),
    (10, "Evaluas tu entorno y sientes que frente a el puedes manejar adecuadamente las exigencias que se derivan de tu relacion con el mundo y quienes te rodean. Entiendes que tienes capacidades para alcanzar tus metas aunque estas requieran de esfuerzo. Tu perspectiva es predominantemente positiva."),
    (13, "Sabes que tus planes pueden tener obstaculos y que las metas que te propones requieren de tu esfuerzo. Aunque reconoces tener capacidades y cualidades para desenvolverte en el entorno, puedes percibir la necesidad de esforzarte un poco mas de lo habitual ante las tareas."),
    (16, "Percibes el mundo como muy exigente, sientes que es dificil alcanzar el exito ya que tienes menos suerte que otras personas. Eso da un tinte de pesimismo a tus planes y perspectiva de vida que se acompana de sentimientos de culpa y sensacion de aislamiento y soledad."),
    (99, "Sientes que frente a los demas eres un ser poco insignificante y poco importante, no te sientes digno, merecedor de atencion o de valoracion por parte de los demas y menos aun de ti mismo. Te sientes aislado de los demas y asumes que es culpa tuya, por lo cual vives tristeza y soledad."),
]

INTERP_DEPRESION_TI_MISMO = [
    (4, "En tu caso, existe una elevada autovaloracion, que se expresa en una actitud optimista y segura de ti mismo/a, considerandote una persona importante y casi libre de defectos o dificultades. Esto puede impedirte ver opciones de mejora y aceptar el fracaso."),
    (7, "Reconoces tu propia importancia, valoras tus capacidades y cualidades. Aunque eres capaz de reconocer algunos de tus defectos, priorizas los aspectos positivos de ti mismo/a y minimizas o justificas tus limitaciones o dificultades, lo que te permite sentirte seguro/a y confiado/a."),
    (10, "Tienes una percepcion clara de ti mismo/a que te lleva a reconocer que tienes areas de fortaleza y posibilidades de desarrollo. Comprendes que esto es propio de todas las personas y, por tanto, te aceptas sin dificultades con cualidades y defectos. Eres capaz de sentirte tan valioso/a como otros."),
    (13, "Tienes un juicio objetivo de ti mismo/a, comprendes que igual que todos, tienes logros y cualidades asi como errores y debilidades. Tu valoracion es en general positiva, pero parece haber predominio de los aspectos negativos sobre los positivos, lo cual puede generar preocupaciones y malestar."),
    (16, "No te sientes lo suficientemente bueno/a o valioso/a, enfatizas en tus errores y sientes que fracasaras en tus propositos. Experimentas insatisfaccion contigo mismo/a y elevados sentimientos de culpa que te impiden disfrutar de la vida. Predominan sentimientos de tristeza."),
    (99, "Tu insatisfaccion contigo mismo/a parece ser constante y marcada, por lo cual te sientes culpable e incapaz. Tu baja valoracion puede generar marcados sentimientos de tristeza y desesperanza."),
]

INTERP_DEPRESION_GENERAL = [
    (4, "Puedes tener un optimismo que parece poco realista y te lleva a una evaluacion un tanto sobredimensionada del futuro que percibes con optimismo. Esto no te permite reconocer las dificultades que puedan presentarse. Tu propia valia parece estar elevada, lo que te impide reconocer posibilidades de mejora y desarrollo."),
    (7, "Encuentras motivacion, iniciativa, alta autovaloracion, seguridad personal y sentimientos de adecuacion contigo mismo/a, las personas y el entorno en el cual te desenvuelves. Ves el futuro de forma optimista y esperanzadora, pero a veces puedes no reconocer las dificultades que puedan surgir."),
    (10, "Tienes una adecuada autovaloracion, seguridad y un optimismo realista y equilibrado. Percibes el entorno y a las personas como valiosos, y evaluas las dificultades como posibilidades de aprender, aportar y obtener logros no solo en el presente, sino tambien en tus planes y proyectos a futuro."),
    (13, "Tu autovaloracion puede verse sesgada por la importancia que das a algunos aspectos negativos de ti mismo/a. Aunque valoras con mas facilidad a los demas y te relacionas adecuadamente, sabes que el optimismo frente al futuro depende de tu esfuerzo y logros, por lo cual eres cauteloso/a al proyectar planes."),
    (16, "Se presenta la presencia de sentimientos depresivos, tristeza y pesimismo, asi como ideas de culpabilidad por los problemas y dificultades que enfrentas y por el impacto que estas tienen en las personas que te rodean. Ves el futuro con marcado pesimismo y desesperanza, y pueden existir ideas de muerte."),
    (99, "Las ideas de tristeza, aislamiento y culpa son marcadas, y tu percepcion de ti mismo/a es de ser una persona llena de defectos que solo aporta dificultades y problemas a quienes te rodean. Esta percepcion te hace ver la vida con marcado pesimismo y no tener planes a futuro. Pueden aparecer ideas o planes suicidas en tu pensamiento. Si sientes esto, es importante buscar ayuda profesional de inmediato."),
]

INTERP_DEPRESION = {
    "Sobre Futuro": INTERP_DEPRESION_FUTURO,
    "Sobre Mundo": INTERP_DEPRESION_MUNDO,
    "Sobre Ti Mismo": INTERP_DEPRESION_TI_MISMO,
}

# ============================================================
# TEXTOS INTERPRETATIVOS - CONGRUENCIA
# ============================================================

INTERP_CONGRUENCIA = {
    "familia_valoracion": [
        (4, "En cuanto a tus relaciones familiares y los vinculos que estableces con los miembros de tu nucleo familiar, es posible que no les des el valor y reconocimiento que merecen. Es posible que los coloques en un lugar de baja prioridad en tu vida."),
        (7, "En general, parece que no le das mucho valor al area familiar y a los vinculos e intercambios que se pueden generar con las personas que forman parte de este grupo. Es posible que no consideres que esta area sea lo suficientemente valiosa como para que ocupe un lugar destacado en tu vida."),
        (10, "Cuando se trata de tu familia y las relaciones que tienes con los miembros de tu nucleo familiar, es posible que les des una valoracion promedio. Aunque las tengas en cuenta, no llegan a ser lo mas valioso e importante para ti como persona."),
        (13, "En tu caso, parece que la familia ocupa un lugar promedio en cuanto a su valoracion. Si bien se encuentra por encima de otras areas en terminos de importancia, no es lo mas relevante en tu vida. Sin embargo, si es considerada importante y se le atribuye un adecuado estatus."),
        (16, "En tu caso, la valoracion que haces de la familia es elevada, lo que indica que le das una gran importancia y le atribuyes un status destacado. Para ti, el concepto de familia y el grupo formado por sus miembros son de gran valor y relevancia en tu vida."),
        (99, "Para ti, la familia es lo mas importante en la escala de valores y por ello le concedes un papel fundamental en tu vida. Consideras que la familia es valiosa y significativa, y por lo tanto, esta por encima de cualquier otra area. En resumen, la familia es el centro y pilar fundamental de tu vida."),
    ],
    "familia_conducta": [
        (4, "En cuanto a tu conducta, no parece que te dirijas a fortalecer los lazos familiares. Es posible que no tengas en cuenta a tu familia en planes, actividades o proyectos, y por lo tanto, no la involucres ni la consultes sobre las decisiones a tomar."),
        (7, "En tus conductas cotidianas parece haber poco interes por integrar a la familia. Es posible que haya baja interaccion entre sus miembros, pobre comunicacion, y que haya minimas acciones y espacios de encuentro y relacion reducidos."),
        (10, "En tu caso, parece que si realizas algunas actividades en las cuales se integra a la familia. Estas actividades pueden permitir establecer vinculos y relaciones que fomentan la comunicacion entre sus miembros."),
        (13, "En cuanto a los proyectos que planteas, parece que tienes en cuenta a tu familia. Ya sea en terminos de participacion activa en los proyectos o como apoyo para la toma de decisiones, es positivo que les permitas tener un rol activo y participativo en estas situaciones."),
        (16, "En tu caso, parece haber un alto interes por integrar a la familia en todos los planes y actividades a desarrollar. Es positivo que les consultes y tengas en cuenta sus opiniones y decisiones."),
        (99, "En tu caso, parece que hay un esfuerzo consciente por incluir a la familia en todas las actividades o proyectos a realizar. Es positivo que les escuches y tomes en cuenta sus ideas y aportes, lo que fomenta un ambiente de comunicacion y colaboracion."),
    ],
    "relacion_valoracion": [
        (4, "En cuanto al intercambio, relacionamiento y participacion con otras personas, independientemente de su procedencia, no parece que sea un tema que tenga importancia para ti."),
        (7, "En tu caso, las relaciones con otros, el involucramiento y la comunicacion parecen ser poco valorados en comparacion con otras areas de desenvolvimiento. Es posible que no les concedas la importancia que merecen."),
        (10, "En tu caso, parece que el area de relaciones interpersonales es valorada y su importancia se ubica en un nivel promedio. Es posible que consideres importante el concepto de comunicarse y tener intercambios con otras personas."),
        (13, "En tu caso, parece que el concepto de relaciones con personas de diversas esferas, como el trabajo, el estudio y la vida social, es considerado importante y valioso. Aunque no sea el area de mayor peso en tu vida, su estatus se encuentra en un nivel promedio."),
        (16, "En tu caso, parece que el relacionamiento con los demas, la posibilidad de conocer, comunicar y establecer vinculos es algo que valoras en gran medida. Es posible que consideres esta area como destacada y valiosa en tu vida."),
        (99, "En tu caso, parece que el area del relacionamiento es la mas importante en tu escala valorativa. Por tanto, los temas que le atanen estan en primer lugar y son considerados muy relevantes en tu vida."),
    ],
    "relacion_conducta": [
        (4, "En tu caso, parece que las demas personas, como colegas, amigos o companeros, no forman parte de tus planes o actividades cotidianas. Es posible que no te interese comunicarte o conocerlos y que prefieras realizar todo de manera independiente e individual."),
        (7, "En tu caso, parece que la interaccion que estableces con las personas de entornos laborales, de estudio o sociales es bastante escasa. Solo en ocasiones especificas y sin mucho interes por la relacion."),
        (10, "En tu caso, parece que buscas incluir a tus colegas, companeros y amigos en actividades de diverso orden, ya sean recreativas, laborales o sociales."),
        (13, "En tu caso, parece que buscas incluir a las personas del entorno en tus planes y proyectos. Ademas, le das importancia a la comunicacion y el intercambio de ideas y opiniones con las personas de tu entorno."),
        (16, "En tu caso, parece que le das una elevada importancia a la realizacion de actividades conjuntas con las personas que te rodean, ya sean amigos, companeros o conocidos."),
        (99, "En tu caso, todos los planes que proyectas tienen en cuenta integrar a amigos, conocidos y nuevas personas. Disfrutas conocer, compartir y realizar actividades conjuntas con personas externas."),
    ],
    "autocuidado_valoracion": [
        (4, "En tu caso, no hay un valor asociado a la idea del autocuidado, ya sea de caracter fisico o emocional. Esta area no tiene un valor destacado y esta relegada, por lo que ocupa el ultimo lugar en tu escala valorativa."),
        (7, "En tu caso, las conductas de cuidado personal en lo que se refiere al cuerpo, la apariencia y el bienestar ocupan un lugar bajo en terminos de la importancia que se les atribuye."),
        (10, "En tu caso, parece que el valor del autocuidado esta ubicado en un nivel promedio tanto en lo que hace referencia a los aspectos del cuerpo, la apariencia y la salud mental."),
        (13, "En tu caso, parece que el area del autocuidado se ubica en la parte alta de la media, lo que indica que le das una importante y valiosa atencion al concepto de prestar atencion a los temas que garantizan la salud integral."),
        (16, "En tu caso, el valor otorgado a los temas de autocuidado, tanto fisico como psicologico, es alto y ubica el area en un lugar elevado por su importancia y el interes que le otorgas."),
        (99, "En tu caso, el status otorgado al autocuidado ubica esta area como la mas importante de todas las implicadas en tu desenvolvimiento, lo que indica que le das una gran relevancia por encima de lo demas."),
    ],
    "autocuidado_conducta": [
        (4, "En tu caso, no existen conductas intencionalmente desarrolladas o planificadas para mantener la salud fisica (como el ejercicio) o mental (como la comunicacion). Ademas, parece que hay poca atencion a temas relacionados con la apariencia, la distraccion o los cuidados en general."),
        (7, "En tu caso, eventualmente pueden encontrarse algunas conductas de cuidado, pero cuando aparecen, se dan de manera aleatoria, sin consistencia, planeacion ni continuidad."),
        (10, "En tu caso, con alguna regularidad realizas conductas de cuidado de ti mismo, las cuales pueden ser de diversa indole, como cuidado de la salud fisica, cuidado de la salud psicologica y cuidado de la apariencia."),
        (13, "En tu caso, estableces prioridades para cuidar y mantener tu salud, lo que indica que le das una gran importancia al autocuidado. Ademas, te preocupas por ser organizado y planificar comportamientos saludables de diversa naturaleza."),
        (16, "En tu caso, te preocupa ser consistente con los habitos y comportamientos saludables que ayudan a mantener tu salud integral. Ademas, planeas y organizas actividades sistematicas y consistentes para el cuidado de tu salud."),
        (99, "En tu caso, tus conductas de autocuidado son cuidadosamente planeadas e incluyen habitos saludables y actividades especificas para mantener tu salud integral. Ademas, sigues rutinas y tienes indicadores claros que te permiten monitorear tu salud integral."),
    ],
    "ocupacional_valoracion": [
        (4, "En tu caso, la ocupacion, ya sea de caracter laboral, de estudio o cualquier otra actividad, no parece ser considerada importante y, por lo tanto, ocupa el ultimo lugar dentro de las areas valoradas."),
        (7, "En tu caso, las areas ocupacionales, constituidas por las labores centrales que se desarrollan en la cotidianidad, como el trabajo o el estudio, parecen tener poca importancia y baja valoracion en comparacion con otras areas y temas."),
        (10, "En tu caso, la valoracion asignada en el area ocupacional senala un valor promedio, lo que indica que se le atribuye una importancia adecuada y equilibrada en relacion a otras areas de tu vida."),
        (13, "En tu caso, el area ocupacional tiene un valor elevado para ti y le atribuyes una importancia media-alta, lo que la identifica como un tema valioso en tu vida, aunque no sea el principal."),
        (16, "En tu caso, el valor otorgado a los temas del ambito ocupacional, como el trabajo, el estudio y otras areas de actividad, es alto, lo que ubica esta area en un lugar importante en tu vida."),
        (99, "En tu caso, se senala que el area ocupacional, ya sea el trabajo o el estudio, es la primera y mas importante en terminos del valor e importancia que le atribuyes para tu desenvolvimiento cotidiano."),
    ],
    "ocupacional_conducta": [
        (4, "En tu caso, no hay interes ni esfuerzo por desarrollar temas o tareas de calidad en el rol que desempenas en el ambito ocupacional, y tampoco hay iniciativa para adquirir nuevos conocimientos o aprendizajes en esta area."),
        (7, "En tu caso, parece que tienes algun interes por hacer nuevos aprendizajes en el area ocupacional y, eventualmente, te esfuerzas para que tus productos y tareas sean de calidad. Sin embargo, estas iniciativas son esporadicas e inconstantes."),
        (10, "En tu caso, parece que realizas tus tareas y responsabilidades de acuerdo con lo establecido, y tambien emprendes acciones de actualizacion y mejoramiento de capacidades en la medida en que se te exigen desde tu rol."),
        (13, "En tu caso, es notable que buscas dar un valor agregado a tus productos y te preocupa por lograr nuevos aprendizajes y mejorar tus habilidades."),
        (16, "En tu caso, es notorio que te interesa innovar, ser disciplinado para aprender y aportar nuevas ideas y estrategias para ampliar tus conocimientos y generar productos de calidad."),
        (99, "En tu caso, es evidente que encaminas todos tus esfuerzos para lograr nuevos aprendizajes y te esmeras por que tus productos se destaquen por la alta calidad. Buscas oportunidades de mejora y actualizacion constantes."),
    ],
}

# ============================================================
# MATRIZ DE CONGRUENCIA
# ============================================================

CONGRUENCIA_MATRIX = [
    {"minVal": 0, "maxVal": 3, "minCon": 0, "maxCon": 3, "result": "MUY ALTO"},
    {"minVal": 0, "maxVal": 3, "minCon": 5, "maxCon": 7, "result": "ALTO"},
    {"minVal": 0, "maxVal": 3, "minCon": 8, "maxCon": 10, "result": "MEDIO ALTO"},
    {"minVal": 0, "maxVal": 3, "minCon": 11, "maxCon": 13, "result": "MEDIO BAJO"},
    {"minVal": 0, "maxVal": 3, "minCon": 14, "maxCon": 16, "result": "BAJO"},
    {"minVal": 0, "maxVal": 3, "minCon": 17, "maxCon": 999, "result": "MUY BAJO"},
    {"minVal": -999, "maxVal": 4, "minCon": 0, "maxCon": 3, "result": "MUY ALTO"},
    {"minVal": -999, "maxVal": 4, "minCon": 5, "maxCon": 7, "result": "ALTO"},
    {"minVal": -999, "maxVal": 4, "minCon": 8, "maxCon": 10, "result": "MEDIO ALTO"},
    {"minVal": -999, "maxVal": 4, "minCon": 11, "maxCon": 13, "result": "MEDIO BAJO"},
    {"minVal": -999, "maxVal": 4, "minCon": 14, "maxCon": 16, "result": "BAJO"},
    {"minVal": -999, "maxVal": 4, "minCon": 17, "maxCon": 999, "result": "MUY BAJO"},
    {"minVal": 5, "maxVal": 7, "minCon": 0, "maxCon": 3, "result": "ALTO"},
    {"minVal": 5, "maxVal": 7, "minCon": 5, "maxCon": 7, "result": "MUY ALTO"},
    {"minVal": 5, "maxVal": 7, "minCon": 8, "maxCon": 10, "result": "ALTO"},
    {"minVal": 5, "maxVal": 7, "minCon": 11, "maxCon": 13, "result": "MEDIO ALTO"},
    {"minVal": 5, "maxVal": 7, "minCon": 14, "maxCon": 16, "result": "MEDIO BAJO"},
    {"minVal": 5, "maxVal": 7, "minCon": 17, "maxCon": 999, "result": "BAJO"},
    {"minVal": 8, "maxVal": 10, "minCon": 0, "maxCon": 3, "result": "MEDIO ALTO"},
    {"minVal": 8, "maxVal": 10, "minCon": 5, "maxCon": 7, "result": "ALTO"},
    {"minVal": 8, "maxVal": 10, "minCon": 8, "maxCon": 10, "result": "MUY ALTO"},
    {"minVal": 8, "maxVal": 10, "minCon": 11, "maxCon": 13, "result": "ALTO"},
    {"minVal": 8, "maxVal": 10, "minCon": 14, "maxCon": 16, "result": "MEDIO ALTO"},
    {"minVal": 8, "maxVal": 10, "minCon": 17, "maxCon": 999, "result": "MEDIO BAJO"},
    {"minVal": 11, "maxVal": 13, "minCon": 0, "maxCon": 3, "result": "MEDIO BAJO"},
    {"minVal": 11, "maxVal": 13, "minCon": 5, "maxCon": 7, "result": "MEDIO ALTO"},
    {"minVal": 11, "maxVal": 13, "minCon": 8, "maxCon": 10, "result": "ALTO"},
    {"minVal": 11, "maxVal": 13, "minCon": 11, "maxCon": 13, "result": "MUY ALTO"},
    {"minVal": 11, "maxVal": 13, "minCon": 14, "maxCon": 16, "result": "ALTO"},
    {"minVal": 11, "maxVal": 13, "minCon": 17, "maxCon": 999, "result": "MEDIO ALTO"},
    {"minVal": 14, "maxVal": 16, "minCon": 0, "maxCon": 3, "result": "BAJO"},
    {"minVal": 14, "maxVal": 16, "minCon": 5, "maxCon": 7, "result": "MEDIO BAJO"},
    {"minVal": 14, "maxVal": 16, "minCon": 8, "maxCon": 10, "result": "MEDIO ALTO"},
    {"minVal": 14, "maxVal": 16, "minCon": 11, "maxCon": 13, "result": "ALTO"},
    {"minVal": 14, "maxVal": 16, "minCon": 14, "maxCon": 16, "result": "MUY ALTO"},
    {"minVal": 14, "maxVal": 16, "minCon": 17, "maxCon": 999, "result": "ALTO"},
    {"minVal": 17, "maxVal": 999, "minCon": 0, "maxCon": 3, "result": "MUY BAJO"},
    {"minVal": 17, "maxVal": 999, "minCon": 5, "maxCon": 7, "result": "BAJO"},
    {"minVal": 17, "maxVal": 999, "minCon": 8, "maxCon": 10, "result": "MEDIO BAJO"},
    {"minVal": 17, "maxVal": 999, "minCon": 11, "maxCon": 13, "result": "MEDIO ALTO"},
    {"minVal": 17, "maxVal": 999, "minCon": 14, "maxCon": 16, "result": "ALTO"},
    {"minVal": 17, "maxVal": 999, "minCon": 17, "maxCon": 999, "result": "MUY ALTO"},
]

# ============================================================
# NIVELES (etiquetas segun rango de puntaje estandarizado)
# ============================================================

NIVELES = [
    (4, "MUY BAJO"),
    (7, "BAJO"),
    (10, "MEDIO BAJO"),
    (13, "MEDIO ALTO"),
    (16, "ALTO"),
    (99, "MUY ALTO"),
]


def obtener_nivel(puntaje_estandarizado):
    for limite, etiqueta in NIVELES:
        if puntaje_estandarizado <= limite:
            return etiqueta
    return "MUY ALTO"


def obtener_interpretacion(puntaje_estandarizado, tabla_interp):
    for limite, texto in tabla_interp:
        if puntaje_estandarizado <= limite:
            return texto
    return tabla_interp[-1][1]


def aplicar_baremo(puntaje_bruto, tabla_baremo):
    return tabla_baremo.get(puntaje_bruto, tabla_baremo.get(max(tabla_baremo.keys()), 0))


def calcular_subdimension(registro, items):
    total = 0
    for col, direccion in items:
        respuesta = registro.get(col)
        total += puntuar_respuesta(respuesta, direccion)
    return total


def calcular_congruencia_nivel(estandarizado_val, estandarizado_con):
    for entry in CONGRUENCIA_MATRIX:
        if (entry["minVal"] <= estandarizado_val <= entry["maxVal"] and
                entry["minCon"] <= estandarizado_con <= entry["maxCon"]):
            return entry["result"]
    return "MEDIO BAJO"


# ============================================================
# FUNCION PRINCIPAL
# ============================================================

def calcular_perfil_adc(datos_respuestas):
    """
    Calcula el perfil psicologico ADC completo a partir de las respuestas crudas.

    Args:
        datos_respuestas: dict con columna -> texto de respuesta
            Ejemplo: {"an18": "De acuerdo", "an19": "Medianamente de acuerdo", ...}

    Returns:
        dict con estructura:
        {
            "ansiedad": { "subdimensiones": {...}, "general": {...} },
            "depresion": { "subdimensiones": {...}, "general": {...} },
            "congruencia": { "areas": {...} }
        }
    """
    resultado = {}

    # --- ANSIEDAD ---
    ansiedad_subdim = {}
    ansiedad_raw_total = 0
    for nombre, items in ANSIEDAD_ITEMS.items():
        raw = calcular_subdimension(datos_respuestas, items)
        ansiedad_raw_total += raw
        estandarizado = aplicar_baremo(raw, BAREMOS_ANSIEDAD[nombre])
        nivel = obtener_nivel(estandarizado)
        interpretacion = obtener_interpretacion(estandarizado, INTERP_ANSIEDAD[nombre])
        ansiedad_subdim[nombre] = {
            "raw": raw,
            "estandarizado": estandarizado,
            "nivel": nivel,
            "interpretacion": interpretacion,
        }

    ans_general_est = aplicar_baremo(ansiedad_raw_total, BAREMO_ANSIEDAD_GENERAL)
    resultado["ansiedad"] = {
        "subdimensiones": ansiedad_subdim,
        "general": {
            "raw": ansiedad_raw_total,
            "estandarizado": ans_general_est,
            "nivel": obtener_nivel(ans_general_est),
            "interpretacion": obtener_interpretacion(ans_general_est, INTERP_ANSIEDAD_GENERAL),
        },
    }

    # --- DEPRESION ---
    depresion_subdim = {}
    depresion_raw_total = 0
    for nombre, items in DEPRESION_ITEMS.items():
        raw = calcular_subdimension(datos_respuestas, items)
        depresion_raw_total += raw
        estandarizado = aplicar_baremo(raw, BAREMOS_DEPRESION[nombre])
        nivel = obtener_nivel(estandarizado)
        interpretacion = obtener_interpretacion(estandarizado, INTERP_DEPRESION[nombre])
        depresion_subdim[nombre] = {
            "raw": raw,
            "estandarizado": estandarizado,
            "nivel": nivel,
            "interpretacion": interpretacion,
        }

    dep_general_est = aplicar_baremo(depresion_raw_total, BAREMO_DEPRESION_GENERAL)
    resultado["depresion"] = {
        "subdimensiones": depresion_subdim,
        "general": {
            "raw": depresion_raw_total,
            "estandarizado": dep_general_est,
            "nivel": obtener_nivel(dep_general_est),
            "interpretacion": obtener_interpretacion(dep_general_est, INTERP_DEPRESION_GENERAL),
        },
    }

    # --- CONGRUENCIA ---
    areas_config = [
        ("Familia", "familia_valoracion", "familia_conducta"),
        ("Relaciones", "relacion_valoracion", "relacion_conducta"),
        ("Autocuidado", "autocuidado_valoracion", "autocuidado_conducta"),
        ("Ocupacional", "ocupacional_valoracion", "ocupacional_conducta"),
    ]

    congruencia_areas = {}
    for nombre_area, key_val, key_con in areas_config:
        raw_val = calcular_subdimension(datos_respuestas, CONGRUENCIA_ITEMS[key_val])
        raw_con = calcular_subdimension(datos_respuestas, CONGRUENCIA_ITEMS[key_con])

        est_val = aplicar_baremo(raw_val, BAREMOS_CONGRUENCIA[key_val])
        est_con = aplicar_baremo(raw_con, BAREMOS_CONGRUENCIA[key_con])

        nivel_congruencia = calcular_congruencia_nivel(est_val, est_con)

        congruencia_areas[nombre_area] = {
            "valoracion": {
                "raw": raw_val,
                "estandarizado": est_val,
                "nivel": obtener_nivel(est_val),
                "interpretacion": obtener_interpretacion(est_val, INTERP_CONGRUENCIA[key_val]),
            },
            "conducta": {
                "raw": raw_con,
                "estandarizado": est_con,
                "nivel": obtener_nivel(est_con),
                "interpretacion": obtener_interpretacion(est_con, INTERP_CONGRUENCIA[key_con]),
            },
            "congruencia": nivel_congruencia,
        }

    resultado["congruencia"] = {"areas": congruencia_areas}

    return resultado
