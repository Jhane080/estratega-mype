"""Modelo estadístico: qué mueve las ventas de la tienda.

Es una regresión lineal. Explica cuántas unidades vende cada producto cada
día a partir de varias cosas a la vez: el día de la semana, la quincena,
los feriados y fechas comerciales, los eventos externos (elecciones, paros,
El Niño), las promociones de la competencia, los descuentos y el contenido
publicado.

¿Por qué todo a la vez y no por separado? Porque se mezclan. Si los reels se
publican más los sábados, comparar "días con reel" contra "días sin reel"
mezcla el efecto del reel con el del sábado. La regresión los separa.

Límite: solo separa lo que está en los datos. Lo que no se mide (por
ejemplo, una ola de calor) no lo ve.
"""

import pandas as pd
import statsmodels.formula.api as smf

from analisis import DIAS_DE_EFECTO, DIAS_SEMANA

TIPOS_DE_EVENTO = ["feriado", "fecha_comercial", "periodo_electoral", "crisis_o_paro", "alerta_fen"]
FORMATOS = ["Reel", "Live", "Carrusel", "Foto", "Historia"]

# Cómo se le explica cada variable al dueño del negocio.
NOMBRES_DE_VARIABLES = {
    "quincena": "Quincena o fin de mes",
    "feriado": "Feriado",
    "fecha_comercial": "Fecha comercial (Cyber Wow, Black Friday, Navidad, Día de la Madre o del Padre)",
    "periodo_electoral": "Campaña electoral",
    "crisis_o_paro": "Paro o crisis política",
    "alerta_fen": "El Niño costero en vigilancia o alerta",
    "promo_competencia": "La competencia lanzó una promoción",
    "con_descuento": "El producto tenía descuento",
    "post_reel": "Hubo un reel del producto",
    "post_live": "Hubo un live del producto",
    "post_carrusel": "Hubo un carrusel del producto",
    "post_foto": "Hubo una foto del producto",
    "post_historia": "Hubo una historia del producto",
    "anios": "Crecimiento por cada año",
}


def leer_calendario(archivo) -> pd.DataFrame:
    return pd.read_csv(archivo, parse_dates=["fecha"])


def leer_competencia(archivo) -> pd.DataFrame:
    return pd.read_csv(archivo, parse_dates=["fecha"])


def armar_tabla_diaria(
    ventas: pd.DataFrame,
    publicaciones: pd.DataFrame,
    calendario: pd.DataFrame,
    competencia: pd.DataFrame,
) -> pd.DataFrame:
    """Una fila por producto y por día, con las ventas y todas las variables.

    Incluye los días en que un producto no vendió nada (unidades = 0). Si solo
    miráramos los días con ventas, el modelo creería que siempre se vende.
    """
    fechas = pd.date_range(ventas["fecha"].min(), ventas["fecha"].max(), freq="D")
    productos = ventas["producto"].unique()
    tabla = pd.MultiIndex.from_product([productos, fechas], names=["producto", "fecha"]).to_frame(index=False)

    # Unidades vendidas y descuento de cada producto cada día.
    por_dia = ventas.groupby(["producto", "fecha"], as_index=False).agg(
        unidades=("cantidad", "sum"),
        descuento=("descuento", "mean"),
    )
    tabla = tabla.merge(por_dia, on=["producto", "fecha"], how="left")
    tabla["unidades"] = tabla["unidades"].fillna(0)

    # El descuento solo se ve en los días con ventas. Para los días sin
    # ventas usamos el descuento más cercano del mismo producto.
    tabla = tabla.sort_values(["producto", "fecha"])
    tabla["descuento"] = tabla.groupby("producto")["descuento"].ffill(limit=3)
    tabla["descuento"] = tabla.groupby("producto")["descuento"].bfill(limit=3)
    tabla["descuento"] = tabla["descuento"].fillna(0)
    tabla["con_descuento"] = (tabla["descuento"] > 0).astype(int)

    # Variables de calendario.
    numero_a_nombre = dict(enumerate(DIAS_SEMANA))
    tabla["dia_semana"] = tabla["fecha"].dt.day_of_week.map(numero_a_nombre)
    tabla["quincena"] = tabla["fecha"].dt.day.isin([1, 15, 16, 30, 31]).astype(int)
    tabla["anios"] = (tabla["fecha"] - tabla["fecha"].min()).dt.days / 365

    for tipo in TIPOS_DE_EVENTO:
        fechas_del_tipo = calendario.loc[calendario["tipo"] == tipo, "fecha"]
        tabla[tipo] = tabla["fecha"].isin(fechas_del_tipo).astype(int)

    dias_con_promo = competencia.loc[competencia["promo_competencia"], "fecha"]
    tabla["promo_competencia"] = tabla["fecha"].isin(dias_con_promo).astype(int)

    # Contenido: ¿hubo un post de este formato sobre este producto en los últimos días?
    # Cada post se "estira" a los días que dura su efecto (el día del post y los 3 siguientes).
    dias_con_efecto = []
    for dias_despues in range(DIAS_DE_EFECTO + 1):
        copia = publicaciones[["producto", "fecha", "formato"]].copy()
        copia["fecha"] = copia["fecha"] + pd.Timedelta(days=dias_despues)
        dias_con_efecto.append(copia)
    dias_con_efecto = pd.concat(dias_con_efecto).drop_duplicates()

    for formato in FORMATOS:
        columna = f"post_{formato.lower()}"
        del_formato = dias_con_efecto[dias_con_efecto["formato"] == formato][["producto", "fecha"]]
        del_formato[columna] = 1
        tabla = tabla.merge(del_formato, on=["producto", "fecha"], how="left")
        tabla[columna] = tabla[columna].fillna(0).astype(int)

    return tabla


def estimar_modelo(tabla: pd.DataFrame) -> pd.DataFrame:
    """Corre la regresión y devuelve una tabla con el efecto de cada variable."""
    variables = list(NOMBRES_DE_VARIABLES)
    formula = (
        "unidades ~ C(producto) + C(dia_semana, Treatment('Lunes')) + "
        + " + ".join(variables)
    )
    resultado = smf.ols(formula, data=tabla).fit()
    intervalos = resultado.conf_int()

    # Un producto vende esto en un día "promedio": sirve para pasar a porcentaje.
    promedio_diario = tabla["unidades"].mean()

    filas = []
    for nombre_tecnico, coeficiente in resultado.params.items():
        if nombre_tecnico in NOMBRES_DE_VARIABLES:
            nombre = NOMBRES_DE_VARIABLES[nombre_tecnico]
            grupo = "Contenido" if nombre_tecnico.startswith("post_") else "Contexto"
        elif nombre_tecnico.startswith("C(dia_semana"):
            dia = nombre_tecnico.split("[T.")[1].rstrip("]")
            nombre = f"{dia} (comparado con un lunes)"
            grupo = "Día de la semana"
        else:
            continue  # los productos y la constante no se muestran

        desde = intervalos.loc[nombre_tecnico, 0]
        hasta = intervalos.loc[nombre_tecnico, 1]
        # Si el rango posible incluye el cero, no podemos decir si sube o baja.
        es_claro = (desde > 0) or (hasta < 0)

        filas.append(
            {
                "variable": nombre_tecnico,
                "que_pasa": nombre,
                "grupo": grupo,
                "efecto": round(coeficiente, 3),
                "efecto_porcentaje": round(100 * coeficiente / promedio_diario, 0),
                "desde": round(desde, 3),
                "hasta": round(hasta, 3),
                "es_claro": es_claro,
            }
        )

    return pd.DataFrame(filas)


def efectos_en_texto(efectos: pd.DataFrame) -> str:
    """Resumen del modelo en texto, para dárselo a Claude."""
    lineas = [
        "Resultados de la regresión (efecto en las ventas diarias de cada producto, "
        "en % frente a un día promedio; 'claro' = el intervalo de 95% no incluye 0):"
    ]
    for fila in efectos.itertuples():
        claro = "claro" if fila.es_claro else "no claro"
        lineas.append(f"- {fila.que_pasa}: {fila.efecto_porcentaje:+.0f}% ({claro})")
    return "\n".join(lineas)


def eventos_proximos(calendario: pd.DataFrame, desde: pd.Timestamp, dias: int = 45) -> pd.DataFrame:
    """Eventos del calendario en los próximos días, uno por evento."""
    hasta = desde + pd.Timedelta(days=dias)
    en_rango = calendario[(calendario["fecha"] >= desde) & (calendario["fecha"] <= hasta)]
    proximos = en_rango.groupby(["evento", "tipo"], as_index=False).agg(
        inicio=("fecha", "min"),
        fin=("fecha", "max"),
    )
    return proximos.sort_values("inicio")
