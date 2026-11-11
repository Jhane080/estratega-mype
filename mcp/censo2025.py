"""Servidor MCP del Censo 2025 del INEI (REDATAM).

El INEI no tiene una API del censo. Su «Procesador Estadístico En-línea»
(REDATAM) recibe un programa por un formulario web, hace el cálculo sobre
toda la población y devuelve la tabla en HTML. Este servidor repite ese mismo
pedido, para que Claude Code pueda consultar el censo con herramientas.

Está adaptado del servidor del Censo 2017 de mi proyecto agente-datos-peru:
el Censo 2025 usa el mismo procesador, solo cambian la dirección y la base
(CPV2025DI), y los nombres de las entidades (POBLACION, DISTRITO...).

    uv run --group mcp mcp/censo2025.py     # el servidor, por stdio (Claude Code lo levanta desde .mcp.json)
"""

import html
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

RAIZ = Path(__file__).parent.parent
CARPETA_SALIDAS = RAIZ / "salidas" / "censo2025"
REDATAM = "https://redatamcpv2025.inei.gob.pe/bininei/RpWebStats.exe"
BASE = "CPV2025DI"
CABECERAS = {"User-Agent": "estratega-mype/0.1"}
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}
NUMERO = re.compile(r"-?\d[\d ]*(,\d+)?%?")

mcp = FastMCP(
    "censo2025",
    instructions=(
        "Censo 2025 del INEI en REDATAM. Usa variables_censo2025 para ver qué variables hay y consultar_censo2025 "
        "para correr un programa REDATAM en el servidor del INEI. No calcules a mano. Los ubigeos son texto de "
        "6 dígitos: '150101', no 150101."
    ),
)


def _sin_tildes(texto):
    return unicodedata.normalize("NFD", str(texto).lower()).encode("ascii", "ignore").decode()


def _texto_html(fragmento):
    return html.unescape(re.sub(r"<[^>]+>", "", fragmento)).replace("\xa0", " ").strip()


def _pedir(url, campos=None):
    for intento in range(3):
        try:
            if campos is None:
                respuesta = httpx.get(url, headers=CABECERAS, timeout=300)
            else:
                respuesta = httpx.post(url, data=campos, headers=CABECERAS, timeout=300)
        except httpx.TransportError:
            time.sleep(3 * (intento + 1))
            continue
        if respuesta.status_code == 200:
            return respuesta.content.decode("utf-8", errors="replace").lstrip("﻿")
        if respuesta.status_code == 500:
            # REDATAM explica el error en la página: «Identificador de variable desconocido...»
            texto = re.sub(r"\s+", " ", _texto_html(respuesta.content.decode("utf-8", errors="replace")))
            motivo = re.search(r"(N\S*mero de Error.*?)(RUNDEF|INL ItemID)", texto)
            detalle = motivo.group(1).strip() if motivo else "sin detalle"
            raise ToolError(
                f"REDATAM rechazó el programa: {detalle}. Revisen los nombres con variables_censo2025 "
                "(respeten mayúsculas: POBLACION.S5_P2) y que las variables nuevas no pasen de 10 caracteres."
            )
        time.sleep(3 * (intento + 1))
    raise ToolError("El servidor REDATAM del INEI no respondió. Esperen unos segundos y reintenten.")


@cache
def diccionario() -> list[dict]:
    pagina = _pedir(f"{REDATAM}/CmdSet?BASE={BASE}&ITEM=PROGRED&lang=esp")
    entidades = {}
    variables = []
    for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", pagina, flags=re.S | re.I):
        celdas = [_texto_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", fila, flags=re.S | re.I)]
        if len(celdas) < 8 or not re.fullmatch(r"\d+(\.\d+)?", celdas[0]):
            continue
        numero, nombre, rotulo, _, grupo, tipo, minimo, maximo = celdas[:8]
        if "." not in numero:
            entidades[numero] = nombre
            continue
        entidad = entidades[numero.split(".")[0]]
        variables.append(
            {
                "variable": f"{entidad}.{nombre}",
                "rotulo": rotulo,
                "grupo": grupo,
                "tipo": tipo,
                "rango": f"{minimo}-{maximo}" if minimo else "",
            }
        )
    return variables


def _es_numero(texto):
    return texto == "-" or NUMERO.fullmatch(texto) is not None


def _a_numero(texto):
    """'5 162 821' -> 5162821, '67,06%' -> 67.06, '-' (cero en REDATAM) -> 0."""
    if texto == "-":
        return 0
    limpio = texto.replace(" ", "").replace("%", "").replace(",", ".")
    return float(limpio) if "." in limpio else int(limpio)


def _tabla(pagina):
    filas = []
    for fila in re.findall(r"<tr>(.*?)</tr>", pagina, flags=re.S):
        celdas = [_texto_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", fila, flags=re.S)]
        celdas = [c for c in celdas if c]
        if celdas:
            filas.append(celdas)

    # Una fila de datos termina en un número; el encabezado es la fila justo antes de la primera de datos.
    posiciones = [i for i, f in enumerate(filas) if len(f) >= 2 and _es_numero(f[-1])]
    if not posiciones:
        return None
    primera = posiciones[0]
    ancho = max(len(filas[i]) for i in posiciones)
    encabezado = filas[primera - 1] if primera > 0 else []
    if len(encabezado) == ancho - 1:
        encabezado = ["categoria"] + encabezado
    if len(encabezado) != ancho:
        encabezado = [f"columna_{j + 1}" for j in range(ancho)]
    columnas = []
    for nombre in encabezado:
        repetido = sum(1 for c in columnas if c == nombre or c.startswith(nombre + "_"))
        columnas.append(nombre if repetido == 0 else f"{nombre}_{repetido + 1}")

    tabla = pd.DataFrame([filas[i] for i in posiciones if len(filas[i]) == ancho], columns=columnas)
    # Una columna es numérica solo si todos sus valores lo son y ninguno empieza con cero: «150101» es un ubigeo.
    for columna in tabla.columns:
        valores = tabla[columna]
        con_cero = valores.str.match(r"0\d").any()
        if valores.map(_es_numero).all() and not con_cero:
            tabla[columna] = valores.map(_a_numero)
    titulo = " · ".join(" ".join(f) for f in filas[: max(primera - 1, 0)])
    return titulo, tabla


def consultar(programa: str, nombre: str = "consulta") -> list[dict]:
    """Corre el programa en el servidor del INEI y guarda cada tabla en salidas/censo2025/<nombre>.csv."""
    if not programa.strip().upper().startswith("RUNDEF"):
        programa = "RUNDEF Job\n    SELECTION ALL\n\n" + programa
    pagina = _pedir(
        f"{REDATAM}/CmdSet?",
        {
            "MAIN": "WebServerMain.inl",
            "BASE": BASE,
            "LANG": "esp",
            "CODIGO": "XXUSUARIOXX",
            "ITEM": "PROGRED",
            "MODE": "RUN",
            "CMDSET": programa,
            "Submit": "Ejecutar",
        },
    )
    # El resultado no viene en la respuesta: viene un iframe que apunta a una tabla temporal por cada TABLE.
    marcos = re.findall(r'<iframe src="([^"]+)"', pagina)
    if not marcos:
        mensaje = re.sub(r"\s+", " ", _texto_html(re.sub(r"<(script|style).*?</\1>", "", pagina, flags=re.S)))
        raise ToolError(f"REDATAM no devolvió tablas. Respuesta del servidor: {mensaje[:300]}")

    nombre = re.sub(r"[^\w-]", "_", nombre)
    CARPETA_SALIDAS.mkdir(parents=True, exist_ok=True)
    tablas = []
    for numero, marco in enumerate(marcos, start=1):
        # En 2025 el iframe trae una ruta relativa ("/redatam//tempo/..."): le agregamos el servidor.
        direccion = html.unescape(marco)
        if direccion.startswith("/"):
            direccion = "https://redatamcpv2025.inei.gob.pe" + direccion
        resultado = _tabla(_pedir(direccion))
        if resultado is None:
            continue
        titulo, tabla = resultado
        sufijo = "" if len(marcos) == 1 else f"_{numero}"
        ruta = CARPETA_SALIDAS / f"{nombre}{sufijo}.csv"
        tabla.to_csv(ruta, index=False, encoding="utf-8")
        tablas.append({"titulo": titulo, "tabla": tabla, "csv": ruta})
    if not tablas:
        raise ToolError("REDATAM respondió, pero la tabla está vacía. Revisen el programa.")
    return tablas


@mcp.tool(annotations=SOLO_LECTURA)
def variables_censo2025(texto: str = "") -> list[dict]:
    """Variables del Censo 2025 que se pueden usar en consultar_censo2025, con su nombre listo para el programa.

    texto filtra por palabras en el nombre, el rótulo o el grupo, sin importar tildes. Ejemplos: "edad", "sexo",
    "agua", "internet", "seguro". Los rótulos empiezan con V: (vivienda), H: (hogar) o P: (persona).
    """
    palabras = _sin_tildes(texto).split()
    encontradas = []
    for variable in diccionario():
        donde = _sin_tildes(f"{variable['variable']} {variable['rotulo']} {variable['grupo']}")
        if all(palabra in donde for palabra in palabras):
            encontradas.append(variable)
    return encontradas


@mcp.tool(annotations=SOLO_LECTURA)
def consultar_censo2025(programa: str, nombre: str = "consulta", max_filas: int = 30) -> dict:
    """Corre un programa REDATAM sobre el Censo 2025 del INEI y devuelve la tabla.

    Entidades, de mayor a menor: PERU2025 > DEPARTAMENTO > PROVINCIA > DISTRITO > VIVIENDA > HOGAR > POBLACION.
    Las variables se escriben ENTIDAD.VARIABLE, tal como las devuelve variables_censo2025 (POBLACION.S5_P2 es el
    sexo, POBLACION.S5_P3 la edad). Si el programa no empieza con RUNDEF, se le agrega
    "RUNDEF Job / SELECTION ALL". Formas que funcionan:

      TABLE T1 AS FREQUENCY OF POBLACION.S5_P2
      DEFINE DISTRITO.NPOB AS COUNT POBLACION TYPE INTEGER
      TABLE T1 AS AREALIST OF DISTRITO, DISTRITO.CCDI, DISTRITO.NCCDI, DISTRITO.NPOB

    Las variables nuevas no pueden pasar de 10 caracteres. AREALIST devuelve el ubigeo como texto. Son conteos del
    censo, sin factor de expansión. La tabla completa queda en salidas/censo2025/<nombre>.csv; la respuesta trae
    las primeras max_filas.
    """
    tablas = consultar(programa, nombre)
    respuesta = []
    for tabla in tablas:
        respuesta.append(
            {
                "titulo": tabla["titulo"],
                "columnas": list(tabla["tabla"].columns),
                "n_filas": len(tabla["tabla"]),
                "filas": tabla["tabla"].head(max_filas).to_dict(orient="records"),
                "csv": tabla["csv"].relative_to(RAIZ).as_posix(),
            }
        )
    return {"tablas": respuesta, "fuente": "INEI, Censos Nacionales 2025, REDATAM (redatamcpv2025.inei.gob.pe)"}


if __name__ == "__main__":
    mcp.run()
