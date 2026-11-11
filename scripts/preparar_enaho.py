"""Resume cuánto gastan los hogares en ropa y calzado, con la ENAHO 2025 del INEI.

La ENAHO es la Encuesta Nacional de Hogares. Pregunta a miles de hogares en
qué gastan su dinero. Aquí usamos el gasto en "vestido y calzado" para
responder una pregunta de marketing: ¿qué hogares gastan más en ropa?

Los microdatos no se suben al repo (pesan mucho y se bajan del INEI). Solo se
guarda el resumen en datos/enaho_vestido_2025.csv.

Cuidado: la ENAHO es representativa por departamento y por dominio
geográfico, NO por distrito. Para distritos se necesita el Censo 2025.

Uso:
    1. Baja la ENAHO 2025 (módulos 34 y 02, en Stata) del portal de
       microdatos del INEI: https://proyectos.inei.gob.pe/microdatos/
    2. uv run python scripts/preparar_enaho.py <carpeta donde quedaron los .dta>
"""

import sys
from pathlib import Path

import pandas as pd

carpeta_enaho = Path(sys.argv[1])
carpeta_datos = Path(__file__).parent.parent / "datos"

NIVELES = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "Rural"}
DOMINIOS = {
    1: "Costa Norte",
    2: "Costa Centro",
    3: "Costa Sur",
    4: "Sierra Norte",
    5: "Sierra Centro",
    6: "Sierra Sur",
    7: "Selva",
    8: "Lima Metropolitana",
}
LLAVE_HOGAR = ["conglome", "vivienda", "hogar"]

# ---------------------------------------------------------------------------
# 1. Hogares: gasto anual en vestido y calzado (gru21hd) y gasto total
# ---------------------------------------------------------------------------
hogares = pd.read_stata(
    next(carpeta_enaho.rglob("sumaria-2025.dta")),
    convert_categoricals=False,
    columns=LLAVE_HOGAR + ["dominio", "estrsocial", "gru21hd", "gashog2d", "factor07"],
)
hogares["nivel"] = hogares["estrsocial"].map(NIVELES)
hogares["region"] = hogares["dominio"].map(DOMINIOS)
# La ENAHO trae el gasto anual. Lo pasamos a mensual, que se entiende mejor.
hogares["gasto_ropa_mes"] = hogares["gru21hd"] / 12
hogares["gasto_total_mes"] = hogares["gashog2d"] / 12

# ---------------------------------------------------------------------------
# 2. Personas: ¿en el hogar vive algún hombre de 18 a 34 años?
#    Es el cliente típico del streetwear masculino.
# ---------------------------------------------------------------------------
personas = pd.read_stata(
    next(carpeta_enaho.rglob("enaho01-2025-200.dta")),
    convert_categoricals=False,
    columns=LLAVE_HOGAR + ["p204", "p207", "p208a"],
)
miembros = personas[personas["p204"] == 1]  # solo quienes son miembros del hogar
hombres_jovenes = miembros[(miembros["p207"] == 1) & (miembros["p208a"].between(18, 34))]
hogares_con_hombre_joven = hombres_jovenes[LLAVE_HOGAR].drop_duplicates()
hogares_con_hombre_joven["tiene_hombre_joven"] = True

hogares = hogares.merge(hogares_con_hombre_joven, on=LLAVE_HOGAR, how="left")
hogares["tiene_hombre_joven"] = hogares["tiene_hombre_joven"].fillna(False)
hogares["con_hombre_joven"] = hogares["tiene_hombre_joven"].map(
    {True: "Con hombres de 18 a 34 años", False: "Sin hombres de 18 a 34 años"}
)


# ---------------------------------------------------------------------------
# 3. Promedios ponderados: cada hogar de la muestra "representa" a factor07 hogares
# ---------------------------------------------------------------------------
def resumir(datos: pd.DataFrame, columna_segmento: str, nombre_tabla: str) -> pd.DataFrame:
    filas = []
    for segmento, grupo in datos.groupby(columna_segmento):
        peso = grupo["factor07"]
        gasto_ropa = (grupo["gasto_ropa_mes"] * peso).sum() / peso.sum()
        gasto_total = (grupo["gasto_total_mes"] * peso).sum() / peso.sum()
        filas.append(
            {
                "tabla": nombre_tabla,
                "segmento": segmento,
                "gasto_ropa_mes": round(gasto_ropa, 1),
                "porcentaje_del_gasto": round(100 * gasto_ropa / gasto_total, 1),
                "hogares": round(peso.sum()),
                "hogares_en_muestra": len(grupo),
            }
        )
    return pd.DataFrame(filas)


lima = hogares[hogares["dominio"] == 8]

resumen = pd.concat(
    [
        resumir(lima, "nivel", "Lima Metropolitana por nivel socioeconómico"),
        resumir(lima, "con_hombre_joven", "Lima Metropolitana por tipo de hogar"),
        resumir(hogares, "region", "Perú por región"),
    ]
)
resumen.to_csv(carpeta_datos / "enaho_vestido_2025.csv", index=False)
print(resumen.to_string(index=False))
print(f"\nGuardado en {carpeta_datos / 'enaho_vestido_2025.csv'}")
