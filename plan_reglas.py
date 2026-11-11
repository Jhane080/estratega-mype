"""Plan de la semana con reglas, sin inteligencia artificial.

Las recomendaciones salen de dos fuentes:
1. Los números de la tienda (qué se vende más, qué está en temporada pasada).
2. Los resultados del modelo (modelo.py): qué formato de contenido, qué días
   y qué contexto mueven las ventas.

Funciona sin clave de API. Devuelve el mismo formato que el plan de Claude
(ia.py), para que la app los muestre igual.
"""

import pandas as pd

from analisis import DIAS_SEMANA

# Ideas de post por formato. {producto} se reemplaza por el nombre del producto.
IDEAS_POR_FORMATO = {
    "Reel": "Reel de 15 segundos en la calle, con el producto puesto y música en tendencia: {producto}.",
    "Live": "Live mostrando de cerca {producto}, respondiendo preguntas, con precio solo para el live.",
    "Carrusel": "Carrusel con 3 formas de combinar: {producto}.",
    "Foto": "Foto con buena luz y el precio en el texto: {producto}.",
    "Historia": "Historia con encuesta de color o talla: {producto}.",
}

FORMATO_DE_VARIABLE = {
    "post_reel": "Reel",
    "post_live": "Live",
    "post_carrusel": "Carrusel",
    "post_foto": "Foto",
    "post_historia": "Historia",
}


def armar_plan_con_reglas(
    ventas: pd.DataFrame,
    efectos: pd.DataFrame,
    proximos_eventos: pd.DataFrame,
    inicio_semana: pd.Timestamp,
) -> dict:
    efecto_de = efectos.set_index("variable")

    # --- Qué impulsar: lo que más vende en los últimos 60 días, de temporada actual.
    ultimos_60_dias = ventas[ventas["fecha"] > ventas["fecha"].max() - pd.Timedelta(days=60)]
    por_producto = ultimos_60_dias.groupby(["producto", "temporada"], as_index=False).agg(
        soles=("total", "sum"), unidades=("cantidad", "sum")
    )
    de_temporada = por_producto[por_producto["temporada"] == "actual"].sort_values("soles", ascending=False)
    productos_a_impulsar = de_temporada["producto"].head(3).tolist()

    que_vender = []
    for fila in de_temporada.head(3).itertuples():
        que_vender.append(
            {
                "producto": fila.producto,
                "por_que": f"Vendiste {fila.unidades:.0f} unidades (S/ {fila.soles:,.0f}) en los últimos 60 días.",
            }
        )

    # --- Formatos de contenido ordenados por efecto (solo los claros y positivos).
    contenido = efectos[efectos["grupo"] == "Contenido"].sort_values("efecto", ascending=False)
    formatos_que_venden = contenido[contenido["es_claro"] & (contenido["efecto"] > 0)]
    formatos_que_no = contenido[~contenido["es_claro"]]

    if len(formatos_que_venden) == 0:
        mejores_formatos = ["Reel"]
    else:
        mejores_formatos = [FORMATO_DE_VARIABLE[variable] for variable in formatos_que_venden["variable"].head(2)]

    # --- Mejores días: según el modelo (el lunes vale 0 porque es la base).
    efecto_por_dia = {"Lunes": 0.0}
    for fila in efectos[efectos["grupo"] == "Día de la semana"].itertuples():
        dia = fila.que_pasa.split(" (")[0]
        efecto_por_dia[dia] = fila.efecto
    dias_ordenados = sorted(efecto_por_dia, key=efecto_por_dia.get, reverse=True)
    peor_dia = dias_ordenados[-1]

    # --- Calendario de contenido: 5 posts en los 5 mejores días de la semana.
    calendario_contenido = []
    for numero, dia in enumerate(DIAS_SEMANA):
        if dia not in dias_ordenados[:5]:
            continue
        formato = mejores_formatos[numero % len(mejores_formatos)]
        producto = productos_a_impulsar[numero % len(productos_a_impulsar)]
        fecha = inicio_semana + pd.Timedelta(days=(numero - inicio_semana.day_of_week) % 7)
        red = "Instagram" if formato != "Live" else "Instagram y TikTok"
        calendario_contenido.append(
            {
                "dia": f"{dia} {fecha.day}/{fecha.month}",
                "red": red,
                "formato": formato,
                "producto": producto,
                "idea": IDEAS_POR_FORMATO[formato].format(producto=producto.lower()),
            }
        )

    # --- Promociones.
    promociones = []
    temporada_pasada = por_producto[por_producto["temporada"] == "pasada"]
    for fila in temporada_pasada.itertuples():
        promociones.append(
            {
                "que": fila.producto,
                "descuento": "Mantener 40%",
                "cuando": "Toda la semana, empujado con un live",
                "por_que": "Es de temporada pasada: hay que liquidarlo. El live es el formato que más ventas trae.",
            }
        )

    if "con_descuento" in efecto_de.index and efecto_de.loc["con_descuento", "es_claro"]:
        menos_vendido = de_temporada.iloc[-1]["producto"]
        porcentaje = efecto_de.loc["con_descuento", "efecto_porcentaje"]
        promociones.append(
            {
                "que": menos_vendido,
                "descuento": "20%",
                "cuando": "Fin de semana de quincena",
                "por_que": f"Es el que menos rota. Tus descuentos suben las ventas del producto en {porcentaje:+.0f}%.",
            }
        )

    if "promo_competencia" in efecto_de.index and efecto_de.loc["promo_competencia", "es_claro"]:
        porcentaje = efecto_de.loc["promo_competencia", "efecto_porcentaje"]
        promociones.append(
            {
                "que": "Respuesta a la competencia",
                "descuento": "Sin bajar precio",
                "cuando": "El día que un competidor lance promoción",
                "por_que": (
                    f"Sus promociones te quitan {abs(porcentaje):.0f}% de ventas ese día. "
                    "En vez de competir por precio, haz un live: suma más de lo que te quitan."
                ),
            }
        )

    for evento in proximos_eventos[proximos_eventos["tipo"] == "fecha_comercial"].itertuples():
        porcentaje = efecto_de.loc["fecha_comercial", "efecto_porcentaje"]
        promociones.append(
            {
                "que": evento.evento,
                "descuento": "Paquetes o 2x1 en accesorios",
                "cuando": f"Del {evento.inicio.day}/{evento.inicio.month} al {evento.fin.day}/{evento.fin.month}",
                "por_que": f"En fechas comerciales vendes {porcentaje:+.0f}%. Prepara stock y contenido desde ahora.",
            }
        )

    # --- Qué evitar.
    que_evitar = []
    for fila in formatos_que_no.itertuples():
        que_evitar.append(
            f"{FORMATO_DE_VARIABLE[fila.variable]}s: casi no mueven ventas "
            f"({fila.efecto_porcentaje:+.0f}%, y el modelo no está seguro de que sea un efecto real)."
        )
    que_evitar.append(f"Publicar lo más importante el {peor_dia.lower()}: es tu día más flojo.")
    if "crisis_o_paro" in efecto_de.index and efecto_de.loc["crisis_o_paro", "es_claro"]:
        porcentaje = efecto_de.loc["crisis_o_paro", "efecto_porcentaje"]
        que_evitar.append(
            f"Lanzar campañas en días de paro o crisis política: tus ventas caen {porcentaje:+.0f}%. "
            "Mejor muévelas un par de días."
        )

    # --- Resumen.
    mejor_formato = mejores_formatos[0]
    variable_mejor = [v for v, f in FORMATO_DE_VARIABLE.items() if f == mejor_formato][0]
    porcentaje_mejor = efecto_de.loc[variable_mejor, "efecto_porcentaje"]
    porcentaje_quincena = efecto_de.loc["quincena", "efecto_porcentaje"]
    resumen = (
        f"Tu mejor herramienta de venta es el {mejor_formato.lower()}: sube las ventas del producto "
        f"en {porcentaje_mejor:+.0f}%. Tus mejores días son {dias_ordenados[0].lower()} y "
        f"{dias_ordenados[1].lower()}, y la quincena suma {porcentaje_quincena:+.0f}%."
    )

    return {
        "resumen": resumen,
        "que_vender": que_vender,
        "promociones": promociones,
        "contenido": calendario_contenido,
        "que_evitar": que_evitar,
    }
