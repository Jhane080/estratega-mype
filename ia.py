"""Las dos llamadas a Claude que usa la app.

1. buscar_tendencias: Claude busca en internet qué está de moda en el rubro
   y qué tiendas online compiten. Usa la herramienta de búsqueda web.
2. armar_plan: Claude junta los números de la tienda con las tendencias y
   devuelve un plan con un formato fijo (salidas estructuradas), para que la
   app lo pueda mostrar ordenado en tablas.

La clave de API se lee de la variable de entorno ANTHROPIC_API_KEY (archivo
.env en local, o "Secrets" en Streamlit Community Cloud). Nunca va en el código.
"""

import json

import anthropic

MODELO = "claude-opus-5-5"

# Si el modelo rechaza una consulta por sus filtros de seguridad, la API la
# reintenta sola con un modelo de respaldo, en vez de dejar la pantalla vacía.
BETAS = ["server-side-fallback-2026-07-01"]


def crear_cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def buscar_tendencias(cliente: anthropic.Anthropic, rubro: str, ciudad: str) -> dict:
    """Busca tendencias y competencia online. Devuelve el texto y las fuentes."""
    pedido = f"""Soy dueño de un negocio de {rubro} en {ciudad}, Perú. Vendo por tienda física,
página web, WhatsApp, Instagram, Facebook y lives.

Busca en internet y respóndeme en español, en Markdown, con estas dos secciones:

## Tendencias
Las 5 tendencias más fuertes ahora mismo para mi rubro en el Perú: productos,
estilos o formatos de contenido que se están moviendo en TikTok, Instagram o
Facebook. Para cada una, una línea de qué es y una de cómo la aprovecharía.

## Competencia online
Hasta 5 tiendas online peruanas que venden lo mismo que yo. Para cada una: qué
venden, en qué rango de precios (si lo encuentras) y qué tipo de contenido hacen.
Si no encuentras un dato, dilo; no lo inventes.

Sé breve. Nada de introducciones."""

    mensajes = [{"role": "user", "content": pedido}]
    herramientas = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": 8,
            "user_location": {"type": "approximate", "country": "PE", "city": ciudad},
        }
    ]

    respuesta = cliente.beta.messages.create(
        model=MODELO,
        max_tokens=16000,
        betas=BETAS,
        fallbacks="default",
        output_config={"effort": "medium"},
        tools=herramientas,
        messages=mensajes,
    )

    # Una búsqueda larga puede pausarse a mitad de camino ("pause_turn").
    # Se le devuelve lo que llevaba para que continúe, hasta 3 veces.
    continuaciones = 0
    while respuesta.stop_reason == "pause_turn" and continuaciones < 3:
        mensajes = [
            {"role": "user", "content": pedido},
            {"role": "assistant", "content": respuesta.content},
        ]
        respuesta = cliente.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            betas=BETAS,
            fallbacks="default",
            output_config={"effort": "medium"},
            tools=herramientas,
            messages=mensajes,
        )
        continuaciones = continuaciones + 1

    if respuesta.stop_reason == "refusal":
        return {"texto": "Claude no pudo responder esta consulta. Prueba con otro rubro.", "fuentes": []}

    texto = ""
    fuentes = {}
    for bloque in respuesta.content:
        if bloque.type != "text":
            continue
        texto = texto + bloque.text
        for cita in bloque.citations or []:
            if cita.type == "web_search_result_location":
                fuentes[cita.url] = cita.title

    lista_fuentes = [{"titulo": titulo, "url": url} for url, titulo in fuentes.items()]
    return {"texto": texto, "fuentes": lista_fuentes}


# Formato fijo del plan: Claude tiene que llenar exactamente estos campos.
FORMATO_DEL_PLAN = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "que_vender": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "producto": {"type": "string"},
                    "por_que": {"type": "string"},
                },
                "required": ["producto", "por_que"],
                "additionalProperties": False,
            },
        },
        "promociones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "que": {"type": "string"},
                    "descuento": {"type": "string"},
                    "cuando": {"type": "string"},
                    "por_que": {"type": "string"},
                },
                "required": ["que", "descuento", "cuando", "por_que"],
                "additionalProperties": False,
            },
        },
        "contenido": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dia": {"type": "string"},
                    "red": {"type": "string"},
                    "formato": {"type": "string"},
                    "producto": {"type": "string"},
                    "idea": {"type": "string"},
                },
                "required": ["dia", "red", "formato", "producto", "idea"],
                "additionalProperties": False,
            },
        },
        "que_evitar": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumen", "que_vender", "promociones", "contenido", "que_evitar"],
    "additionalProperties": False,
}


def armar_plan(cliente: anthropic.Anthropic, rubro: str, resumen_tienda: str, tendencias: str) -> dict:
    """Pide a Claude el plan de la próxima semana, con formato fijo."""
    if tendencias == "":
        tendencias = "(No se buscaron tendencias. Basa el plan solo en los datos de la tienda.)"

    pedido = f"""Eres el analista de marketing de una MYPE peruana de {rubro}. El dueño no tiene
tiempo ni formación en datos: háblale claro, en español peruano, sin jerga.

Estos son los números reales de su tienda:
<datos_tienda>
{resumen_tienda}
</datos_tienda>

Esto es lo que se encontró en internet sobre tendencias y competencia:
<tendencias>
{tendencias}
</tendencias>

Arma el plan para la próxima semana:
- resumen: 2 o 3 frases con lo más importante que muestran los datos.
- que_vender: 3 productos a impulsar, cada uno con el dato que lo justifica.
- promociones: 2 o 3 promociones concretas (qué producto o categoría, cuánto
  descuento, qué día) y por qué. Los productos de temporada pasada se pueden
  liquidar; no regales margen en lo que ya se vende solo.
- contenido: un calendario de 5 publicaciones (día, red, formato, producto e
  idea concreta del post). Prioriza los formatos y redes que más ventas
  extra trajeron según los datos.
- que_evitar: 2 o 3 cosas que hoy no le están funcionando.

Cada recomendación tiene que apoyarse en un número de los datos o en una
tendencia encontrada. No inventes cifras."""

    respuesta = cliente.beta.messages.create(
        model=MODELO,
        max_tokens=16000,
        betas=BETAS,
        fallbacks="default",
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": FORMATO_DEL_PLAN},
        },
        messages=[{"role": "user", "content": pedido}],
    )

    if respuesta.stop_reason == "refusal":
        return {}

    texto = ""
    for bloque in respuesta.content:
        if bloque.type == "text":
            texto = texto + bloque.text
    return json.loads(texto)
