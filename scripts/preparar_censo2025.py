"""Cuántos hombres de 18 a 34 años viven en cada distrito, según el Censo 2025.

Es el cliente típico del streetwear masculino. Con esto la app puede decir en
qué distritos de Lima y Callao está el mercado.

Usa la misma función que el servidor MCP (mcp/censo2025.py): manda un
programa REDATAM al servidor del INEI y guarda la tabla.

Uso:
    uv run --group mcp python scripts/preparar_censo2025.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "mcp"))

import censo2025  # noqa: E402  (se importa después de agregar la carpeta mcp/ al camino)

# Conteos por distrito. Las variables nuevas no pueden pasar de 10 caracteres.
PROGRAMA = """
DEFINE DISTRITO.NPOB AS COUNT POBLACION TYPE INTEGER
DEFINE DISTRITO.NHOMJOV AS COUNT POBLACION FOR POBLACION.S5_P2 = 1 AND POBLACION.S5_P3 >= 18 AND POBLACION.S5_P3 <= 34 TYPE INTEGER
DEFINE DISTRITO.NMUJJOV AS COUNT POBLACION FOR POBLACION.S5_P2 = 2 AND POBLACION.S5_P3 >= 18 AND POBLACION.S5_P3 <= 34 TYPE INTEGER
TABLE T1 AS AREALIST OF DISTRITO, DISTRITO.CCDI, DISTRITO.NCCDI, DISTRITO.NPOB, DISTRITO.NHOMJOV, DISTRITO.NMUJJOV
"""

tablas = censo2025.consultar(PROGRAMA, nombre="distritos_jovenes")
tabla = tablas[0]["tabla"]
print(tabla.columns.tolist())
print(tabla.head())
print(f"{len(tabla)} distritos")

# Nos quedamos con Lima Metropolitana y Callao. Ojo: en esta base del Censo 2025,
# Lima Metropolitana tiene código 27 (provincia 2701) y la Región Lima 26, no el
# 15 de siempre. El Callao sigue siendo 07 (provincia 0701).
# REDATAM devuelve: Código (ubigeo), Distrito (2 dígitos), Distrito: (nombre) y los tres conteos.
tabla = tabla.iloc[:, [0, 2, 3, 4, 5]].copy()
tabla.columns = ["ubigeo", "distrito", "poblacion", "hombres_18_34", "mujeres_18_34"]
tabla["ubigeo"] = tabla["ubigeo"].astype(str).str.zfill(6)  # el ubigeo es texto de 6 dígitos, siempre
lima_callao = tabla[tabla["ubigeo"].str.startswith(("2701", "0701"))].copy()
# El nombre viene como "Lima Metropolitana, Lima, distrito: Miraflores": nos quedamos con "Miraflores".
lima_callao["distrito"] = lima_callao["distrito"].str.split("distrito: ").str[-1]
lima_callao["porcentaje_hombres_18_34"] = (100 * lima_callao["hombres_18_34"] / lima_callao["poblacion"]).round(1)
lima_callao = lima_callao.sort_values("hombres_18_34", ascending=False)

ruta = RAIZ / "datos" / "censo2025_lima_callao.csv"
lima_callao.to_csv(ruta, index=False)
print(lima_callao.head(10).to_string(index=False))
print(f"Guardado en {ruta}")
