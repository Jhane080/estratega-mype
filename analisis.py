"""Cálculos sobre las ventas y las publicaciones de la tienda.

Aquí no hay inteligencia artificial: solo pandas. Primero se ordenan los
números y después se le pasan a Claude ya resumidos, porque así gasta menos
y se equivoca menos que si lee miles de filas.
"""

import pandas as pd

# Días que se miran después de cada publicación para ver si empujó ventas.
DIAS_DE_EFECTO = 3

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def leer_ventas(archivo) -> pd.DataFrame:
    ventas = pd.read_csv(archivo, parse_dates=["fecha"])
    # day_of_week da 0 para lunes, 1 para martes... y lo traducimos al nombre.
    numero_a_nombre = dict(enumerate(DIAS_SEMANA))
    ventas["dia_semana"] = ventas["fecha"].dt.day_of_week.map(numero_a_nombre)
    return ventas


def leer_publicaciones(archivo) -> pd.DataFrame:
    return pd.read_csv(archivo, parse_dates=["fecha"])


def revisar_si_hay_datos_suficientes(ventas: pd.DataFrame, publicaciones: pd.DataFrame) -> list[str]:
    """Devuelve la lista de cosas que faltan. Si está vacía, se puede recomendar.

    Con pocos datos cualquier "patrón" puede ser casualidad. Preferimos decir
    "todavía no sé" antes que dar una recomendación inventada.
    """
    faltantes = []

    dias_con_ventas = ventas["fecha"].nunique()
    if dias_con_ventas < 28:
        faltantes.append(
            f"Hay ventas de {dias_con_ventas} días. Se necesitan al menos 28 "
            "(4 semanas) para ver qué días se vende más."
        )

    if len(publicaciones) < 12:
        faltantes.append(
            f"Hay {len(publicaciones)} publicaciones. Se necesitan al menos 12 "
            "para comparar qué tipo de contenido vende más."
        )

    publicaciones_por_formato = publicaciones["formato"].value_counts()
    formatos_con_datos = publicaciones_por_formato[publicaciones_por_formato >= 3]
    if len(formatos_con_datos) < 2:
        faltantes.append(
            "Se necesitan al menos 3 publicaciones de 2 formatos distintos "
            "(por ejemplo, reels y fotos) para poder compararlos."
        )

    return faltantes


def ventas_por_producto(ventas: pd.DataFrame) -> pd.DataFrame:
    tabla = ventas.groupby(["producto", "categoria", "temporada"], as_index=False).agg(
        unidades=("cantidad", "sum"),
        soles=("total", "sum"),
    )
    return tabla.sort_values("soles", ascending=False)


def ventas_por_canal(ventas: pd.DataFrame) -> pd.DataFrame:
    tabla = ventas.groupby("canal", as_index=False).agg(soles=("total", "sum"))
    return tabla.sort_values("soles", ascending=False)


def ventas_por_dia_semana(ventas: pd.DataFrame) -> pd.DataFrame:
    # Promedio por día, no suma: si hubo más sábados que lunes, la suma engaña.
    ventas_diarias = ventas.groupby(["fecha", "dia_semana"], as_index=False).agg(soles=("total", "sum"))
    tabla = ventas_diarias.groupby("dia_semana", as_index=False).agg(soles_promedio=("soles", "mean"))
    tabla["orden"] = tabla["dia_semana"].map(DIAS_SEMANA.index)
    return tabla.sort_values("orden").drop(columns="orden")


def efecto_de_cada_publicacion(ventas: pd.DataFrame, publicaciones: pd.DataFrame) -> pd.DataFrame:
    """Para cada publicación, cuánto vendió su producto en los días siguientes.

    Se compara con lo que ese producto vende en un día normal. Si el producto
    suele vender 1 por día y en los 4 días después del reel vendió 9, el reel
    "trajo" unas 5 unidades extra.
    """
    unidades_por_dia = ventas.groupby(["producto", "fecha"])["cantidad"].sum()
    total_dias = ventas["fecha"].nunique()
    promedio_diario = ventas.groupby("producto")["cantidad"].sum() / total_dias

    filas = []
    for publicacion in publicaciones.itertuples():
        inicio = publicacion.fecha
        fin = inicio + pd.Timedelta(days=DIAS_DE_EFECTO)

        ventas_del_producto = unidades_por_dia.get(publicacion.producto, pd.Series(dtype=float))
        en_la_ventana = ventas_del_producto[
            (ventas_del_producto.index >= inicio) & (ventas_del_producto.index <= fin)
        ]
        unidades_despues = en_la_ventana.sum()

        unidades_normales = promedio_diario.get(publicacion.producto, 0) * (DIAS_DE_EFECTO + 1)

        filas.append(
            {
                "fecha": publicacion.fecha.date(),
                "red": publicacion.red,
                "formato": publicacion.formato,
                "producto": publicacion.producto,
                "alcance": publicacion.alcance,
                "unidades_despues": int(unidades_despues),
                "unidades_extra": round(unidades_despues - unidades_normales, 1),
            }
        )

    return pd.DataFrame(filas)


def resumen_por_formato(efecto: pd.DataFrame) -> pd.DataFrame:
    tabla = efecto.groupby("formato", as_index=False).agg(
        publicaciones=("producto", "count"),
        unidades_extra_promedio=("unidades_extra", "mean"),
        alcance_promedio=("alcance", "mean"),
    )
    tabla["unidades_extra_promedio"] = tabla["unidades_extra_promedio"].round(1)
    tabla["alcance_promedio"] = tabla["alcance_promedio"].round(0)
    return tabla.sort_values("unidades_extra_promedio", ascending=False)


def resumen_por_red(efecto: pd.DataFrame) -> pd.DataFrame:
    tabla = efecto.groupby("red", as_index=False).agg(
        publicaciones=("producto", "count"),
        unidades_extra_promedio=("unidades_extra", "mean"),
    )
    tabla["unidades_extra_promedio"] = tabla["unidades_extra_promedio"].round(1)
    return tabla.sort_values("unidades_extra_promedio", ascending=False)


def resumen_en_texto(ventas: pd.DataFrame, efecto: pd.DataFrame) -> str:
    """Arma un resumen corto en texto para dárselo a Claude."""
    productos = ventas_por_producto(ventas)
    canales = ventas_por_canal(ventas)
    dias = ventas_por_dia_semana(ventas)
    formatos = resumen_por_formato(efecto)
    redes = resumen_por_red(efecto)

    fecha_inicio = ventas["fecha"].min().date()
    fecha_fin = ventas["fecha"].max().date()

    partes = [
        f"Periodo: {fecha_inicio} a {fecha_fin}.",
        f"Ventas totales: S/ {ventas['total'].sum():,.0f} en {ventas['pedido'].nunique()} pedidos.",
        "",
        "Ventas por producto (unidades, soles, temporada):",
        productos.to_string(index=False),
        "",
        "Ventas por canal:",
        canales.to_string(index=False),
        "",
        "Venta promedio por día de la semana:",
        dias.to_string(index=False),
        "",
        f"Efecto del contenido: unidades extra vendidas del producto en los {DIAS_DE_EFECTO + 1} días "
        "desde la publicación, frente a un periodo normal. Por formato:",
        formatos.to_string(index=False),
        "",
        "Por red social:",
        redes.to_string(index=False),
    ]
    return "\n".join(partes)
