"""Estratega MYPE: el analista de marketing que una MYPE no puede contratar.

Para correrla en tu computadora:
    uv run streamlit run app.py
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import analisis
import ia
import modelo
import plan_reglas

st.set_page_config(page_title="Estratega MYPE", page_icon=":material/insights:", layout="wide")

# La clave de API: en local viene del archivo .env; en Streamlit Community
# Cloud, de la sección "Secrets". Nunca se escribe en el código.
load_dotenv()
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except FileNotFoundError:
    pass
hay_clave = bool(os.environ.get("ANTHROPIC_API_KEY"))

CARPETA_DATOS = Path(__file__).parent / "datos"
ARCHIVO_EJEMPLO_TENDENCIAS = CARPETA_DATOS / "ejemplo_tendencias.md"

# Para el modelo se necesitan al menos 6 meses: menos que eso y no hay
# suficientes quincenas, feriados ni posts de cada tipo para comparar.
DIAS_MINIMOS_PARA_MODELO = 180

if "tendencias" not in st.session_state:
    st.session_state["tendencias"] = None
if "plan_claude" not in st.session_state:
    st.session_state["plan_claude"] = None


# El modelo tarda unos segundos: se guarda para no recalcularlo en cada clic.
@st.cache_data(show_spinner=False)
def efectos_del_modelo(
    ventas: pd.DataFrame,
    publicaciones: pd.DataFrame,
    calendario: pd.DataFrame,
    competencia: pd.DataFrame,
) -> pd.DataFrame:
    tabla = modelo.armar_tabla_diaria(ventas, publicaciones, calendario, competencia)
    return modelo.estimar_modelo(tabla)


# Las llamadas a Claude cuestan plata. Se guardan 6 horas: si se pide lo mismo
# otra vez (por ejemplo, en el ensayo y en la presentación), no se paga dos veces.
@st.cache_data(ttl="6h", show_spinner=False)
def tendencias_guardadas(rubro: str, ciudad: str) -> dict:
    return ia.buscar_tendencias(ia.crear_cliente(), rubro, ciudad)


@st.cache_data(ttl="6h", show_spinner=False)
def plan_de_claude(rubro: str, resumen_tienda: str, tendencias: str) -> dict:
    return ia.armar_plan(ia.crear_cliente(), rubro, resumen_tienda, tendencias)


def mostrar_plan(plan: dict, clave: str) -> None:
    st.info(plan["resumen"], title="En resumen", icon=":material/lightbulb:")

    st.subheader(":material/sell: Qué impulsar")
    with st.container(horizontal=True):
        for recomendacion in plan["que_vender"]:
            with st.container(border=True):
                st.markdown(f"**{recomendacion['producto']}**")
                st.caption(recomendacion["por_que"])

    st.subheader(":material/percent: Promociones")
    st.dataframe(
        pd.DataFrame(plan["promociones"]).rename(
            columns={"que": "Qué", "descuento": "Descuento", "cuando": "Cuándo", "por_que": "Por qué"}
        ),
        hide_index=True,
        alt="Promociones recomendadas",
    )

    st.subheader(":material/calendar_month: Calendario de contenido")
    calendario_contenido = pd.DataFrame(plan["contenido"]).rename(
        columns={"dia": "Día", "red": "Red", "formato": "Formato", "producto": "Producto", "idea": "Idea"}
    )
    st.dataframe(calendario_contenido, hide_index=True, alt="Calendario de contenido de la semana")
    st.download_button(
        "Descargar calendario",
        data=calendario_contenido.to_csv(index=False).encode("utf-8"),
        file_name="calendario_contenido.csv",
        icon=":material/download:",
        key=f"descargar_{clave}",
    )

    st.subheader(":material/block: Qué dejar de hacer")
    for consejo in plan["que_evitar"]:
        st.markdown(f"- {consejo}")


# ---------------------------------------------------------------------------
# Barra lateral: de qué negocio se trata y de dónde vienen los datos
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Tu negocio")
    rubro = st.text_input("Rubro", value="streetwear masculino")
    ciudad = st.text_input("Ciudad", value="Lima")

    st.header("Tus datos")
    origen = st.segmented_control(
        "Origen de los datos",
        options=["Datos de ejemplo", "Subir mis archivos"],
        default="Datos de ejemplo",
        required=True,
    )

    if origen == "Subir mis archivos":
        archivo_ventas = st.file_uploader("Ventas (CSV)", type="csv")
        archivo_publicaciones = st.file_uploader("Publicaciones (CSV)", type="csv")
        archivo_competencia = st.file_uploader("Promociones de la competencia (CSV, opcional)", type="csv")
        st.caption("Descarga los ejemplos para ver qué columnas necesita cada archivo.")
        for nombre_archivo in ["ventas_ejemplo.csv", "publicaciones_ejemplo.csv", "competencia_ejemplo.csv"]:
            st.download_button(
                nombre_archivo,
                data=(CARPETA_DATOS / nombre_archivo).read_bytes(),
                file_name=nombre_archivo,
                icon=":material/download:",
            )
    else:
        archivo_ventas = CARPETA_DATOS / "ventas_ejemplo.csv"
        archivo_publicaciones = CARPETA_DATOS / "publicaciones_ejemplo.csv"
        archivo_competencia = CARPETA_DATOS / "competencia_ejemplo.csv"
        st.caption(
            "Ventas, publicaciones y promociones de la competencia **inventadas** para una tienda de "
            "streetwear, a partir de una entrevista real con su dueño. El calendario de eventos "
            "(feriados, elecciones, paros, El Niño) es **real**."
        )

st.title("Estratega MYPE")
st.caption("Tu analista de marketing: qué vender, qué promocionar y qué publicar la próxima semana.")

if archivo_ventas is None or archivo_publicaciones is None:
    st.info("Sube tus archivos de ventas y publicaciones en la barra lateral para empezar.", icon=":material/upload_file:")
    st.stop()

ventas = analisis.leer_ventas(archivo_ventas)
publicaciones = analisis.leer_publicaciones(archivo_publicaciones)
calendario = modelo.leer_calendario(CARPETA_DATOS / "calendario_eventos.csv")
if archivo_competencia is None:
    competencia = pd.DataFrame({"fecha": pd.to_datetime([]), "promo_competencia": pd.Series([], dtype=bool)})
else:
    competencia = modelo.leer_competencia(archivo_competencia)

efecto = analisis.efecto_de_cada_publicacion(ventas, publicaciones)
dias_de_datos = ventas["fecha"].nunique()
inicio_semana = ventas["fecha"].max() + pd.Timedelta(days=1)

# Antes de recomendar nada, revisamos si hay datos suficientes.
faltantes = analisis.revisar_si_hay_datos_suficientes(ventas, publicaciones)
if dias_de_datos < DIAS_MINIMOS_PARA_MODELO:
    faltantes.append(
        f"El modelo necesita al menos {DIAS_MINIMOS_PARA_MODELO} días de ventas (6 meses); tienes {dias_de_datos}."
    )
if faltantes:
    st.warning(
        "\n".join(f"- {faltante}" for faltante in faltantes)
        + "\n\nPuedes ver tus números, pero el modelo y el plan se activan cuando haya datos suficientes.",
        title="Todavía faltan datos para recomendar",
        icon=":material/hourglass_top:",
    )

(
    pestana_ventas,
    pestana_contenido,
    pestana_modelo,
    pestana_cliente,
    pestana_tendencias,
    pestana_plan,
) = st.tabs(
    [
        ":material/payments: Ventas",
        ":material/movie: Contenido que vende",
        ":material/query_stats: Qué mueve tus ventas",
        ":material/groups: Tu cliente objetivo",
        ":material/trending_up: Tendencias y competencia",
        ":material/event_note: Plan de la semana",
    ]
)

# ---------------------------------------------------------------------------
# 1. Ventas
# ---------------------------------------------------------------------------
with pestana_ventas:
    por_producto = analisis.ventas_por_producto(ventas)
    producto_estrella = por_producto.iloc[0]["producto"]
    total_soles = ventas["total"].sum()
    total_pedidos = ventas["pedido"].nunique()

    st.caption(f"Del {ventas['fecha'].min():%d/%m/%Y} al {ventas['fecha'].max():%d/%m/%Y}.")
    with st.container(horizontal=True):
        st.metric("Ventas", f"S/ {total_soles:,.0f}", border=True)
        st.metric("Pedidos", f"{total_pedidos:,}", border=True)
        st.metric("Ticket promedio", f"S/ {total_soles / total_pedidos:,.0f}", border=True)
        st.metric("Producto estrella", producto_estrella, border=True)

    with st.container(border=True):
        st.subheader("Ventas por semana")
        ventas_semanales = ventas.set_index("fecha").resample("W")["total"].sum().reset_index()
        st.line_chart(ventas_semanales, x="fecha", y="total", x_label="", y_label="Soles", alt="Ventas por semana")

    columna_izquierda, columna_derecha = st.columns(2)
    with columna_izquierda:
        with st.container(border=True):
            st.subheader("Qué se vende más")
            st.bar_chart(
                por_producto,
                x="producto",
                y="soles",
                horizontal=True,
                sort="-soles",
                x_label="Soles",
                y_label="",
                alt="Ventas en soles por producto",
            )
    with columna_derecha:
        with st.container(border=True):
            st.subheader("Por dónde se vende")
            st.bar_chart(
                analisis.ventas_por_canal(ventas),
                x="canal",
                y="soles",
                horizontal=True,
                sort="-soles",
                x_label="Soles",
                y_label="",
                alt="Ventas en soles por canal",
            )

# ---------------------------------------------------------------------------
# 2. Contenido que vende (comparación simple: antes y después de cada post)
# ---------------------------------------------------------------------------
with pestana_contenido:
    st.markdown(
        f"Para cada publicación miramos cuánto se vendió **ese producto** en los "
        f"{analisis.DIAS_DE_EFECTO + 1} días siguientes, y lo comparamos con lo que vende "
        "en días normales. La diferencia son las **unidades extra** que trajo el post."
    )

    por_formato = analisis.resumen_por_formato(efecto)
    mejor_formato = por_formato.iloc[0]

    st.success(
        f"Tus **{mejor_formato['formato'].lower()}s** traen en promedio "
        f"**{mejor_formato['unidades_extra_promedio']} unidades extra** por publicación.",
        title="Lo que mejor te funciona",
        icon=":material/star:",
    )

    columna_izquierda, columna_derecha = st.columns(2)
    with columna_izquierda:
        with st.container(border=True):
            st.subheader("Por formato")
            st.bar_chart(
                por_formato,
                x="formato",
                y="unidades_extra_promedio",
                sort="-unidades_extra_promedio",
                x_label="",
                y_label="Unidades extra por post",
                alt="Unidades extra vendidas por formato de publicación",
            )
    with columna_derecha:
        with st.container(border=True):
            st.subheader("Por red social")
            st.bar_chart(
                analisis.resumen_por_red(efecto),
                x="red",
                y="unidades_extra_promedio",
                sort="-unidades_extra_promedio",
                x_label="",
                y_label="Unidades extra por post",
                alt="Unidades extra vendidas por red social",
            )

    with st.expander("Ver cada publicación"):
        st.dataframe(
            efecto.sort_values("unidades_extra", ascending=False),
            hide_index=True,
            alt="Unidades extra vendidas después de cada publicación",
        )

# ---------------------------------------------------------------------------
# 3. Qué mueve tus ventas (regresión)
# ---------------------------------------------------------------------------
efectos = None
if dias_de_datos >= DIAS_MINIMOS_PARA_MODELO:
    with st.spinner("Calculando el modelo..."):
        efectos = efectos_del_modelo(ventas, publicaciones, calendario, competencia)

with pestana_modelo:
    st.markdown(
        "Un **modelo estadístico** (regresión) mira todos tus días a la vez y separa qué parte de las "
        "ventas se debe a cada cosa: el contenido, el día, la quincena, las fechas comerciales y lo que "
        "pasa afuera (elecciones, paros, El Niño, la competencia)."
    )
    if efectos is None:
        st.info("El modelo se activa con al menos 6 meses de ventas.", icon=":material/hourglass_top:")
    else:
        efectos_claros = efectos[efectos["es_claro"]].copy()
        efectos_claros["que_pasa"] = efectos_claros["que_pasa"].str.slice(0, 45)

        with st.container(border=True):
            st.subheader("Cuánto cambian tus ventas cuando...")
            st.caption(
                "Porcentaje frente a un día promedio de cada producto. Solo se muestran los efectos "
                "de los que el modelo está seguro."
            )
            st.bar_chart(
                efectos_claros,
                x="que_pasa",
                y="efecto_porcentaje",
                horizontal=True,
                sort="-efecto_porcentaje",
                x_label="% de cambio en las ventas",
                y_label="",
                alt="Efecto de cada variable en las ventas diarias",
            )

        with st.expander("Ver la tabla completa del modelo"):
            st.caption(
                "**Efecto**: unidades extra por producto y por día. **Desde / hasta**: rango donde "
                "está el efecto real con 95% de confianza. Si el rango cruza el cero, no es claro."
            )
            st.dataframe(
                efectos.drop(columns=["variable"]).rename(
                    columns={
                        "que_pasa": "Cuando...",
                        "grupo": "Grupo",
                        "efecto": "Efecto",
                        "efecto_porcentaje": "Efecto (%)",
                        "desde": "Desde",
                        "hasta": "Hasta",
                        "es_claro": "¿Es claro?",
                    }
                ),
                hide_index=True,
                alt="Resultados completos de la regresión",
            )

        st.caption(
            "Ojo: el modelo encuentra asociaciones. Solo separa lo que está en los datos; si algo "
            "importante no se mide, se lo puede atribuir a otra variable."
        )

# ---------------------------------------------------------------------------
# 4. Tu cliente objetivo (ENAHO 2025 del INEI: datos reales y públicos)
# ---------------------------------------------------------------------------
with pestana_cliente:
    st.markdown(
        "¿Qué hogares gastan más en ropa y calzado? Lo responde la **Encuesta Nacional de Hogares "
        "(ENAHO) 2025 del INEI**, con datos reales de miles de hogares de todo el país."
    )
    enaho = pd.read_csv(CARPETA_DATOS / "enaho_vestido_2025.csv")
    por_nivel = enaho[enaho["tabla"] == "Lima Metropolitana por nivel socioeconómico"]
    por_hogar = enaho[enaho["tabla"] == "Lima Metropolitana por tipo de hogar"]
    por_region = enaho[enaho["tabla"] == "Perú por región"]

    con_joven = por_hogar[por_hogar["segmento"].str.startswith("Con")].iloc[0]
    sin_joven = por_hogar[por_hogar["segmento"].str.startswith("Sin")].iloc[0]
    diferencia = 100 * (con_joven["gasto_ropa_mes"] / sin_joven["gasto_ropa_mes"] - 1)

    st.success(
        f"En Lima, los hogares **con hombres de 18 a 34 años** gastan **S/ {con_joven['gasto_ropa_mes']:.0f} "
        f"al mes** en ropa y calzado, **{diferencia:.0f}% más** que los hogares sin ellos "
        f"(S/ {sin_joven['gasto_ropa_mes']:.0f}). Son {con_joven['hogares']:,.0f} hogares: ese es tu mercado.",
        title="Tu cliente está en hogares con hombres jóvenes",
        icon=":material/target:",
    )

    columna_izquierda, columna_derecha = st.columns(2)
    with columna_izquierda:
        with st.container(border=True):
            st.subheader("Lima: gasto en ropa por nivel socioeconómico")
            st.caption("Soles al mes por hogar.")
            st.bar_chart(
                por_nivel,
                x="segmento",
                y="gasto_ropa_mes",
                sort=False,
                x_label="Nivel socioeconómico",
                y_label="Soles al mes",
                alt="Gasto mensual en ropa por nivel socioeconómico en Lima",
            )
    with columna_derecha:
        with st.container(border=True):
            st.subheader("Perú: gasto en ropa por región")
            st.caption("Soles al mes por hogar. Útil si vendes con envíos a provincia.")
            st.bar_chart(
                por_region,
                x="segmento",
                y="gasto_ropa_mes",
                horizontal=True,
                sort="-gasto_ropa_mes",
                x_label="Soles al mes",
                y_label="",
                alt="Gasto mensual en ropa por región del Perú",
            )

    censo = pd.read_csv(CARPETA_DATOS / "censo2025_lima_callao.csv", dtype={"ubigeo": str})
    with st.container(border=True):
        st.subheader("¿Dónde viven? Hombres de 18 a 34 años por distrito")
        st.caption("Lima Metropolitana y Callao, Censo 2025 (INEI). Los 15 distritos con más hombres jóvenes.")
        st.bar_chart(
            censo.head(15),
            x="distrito",
            y="hombres_18_34",
            horizontal=True,
            sort="-hombres_18_34",
            x_label="Hombres de 18 a 34 años",
            y_label="",
            alt="Distritos de Lima y Callao con más hombres de 18 a 34 años",
        )
        with st.expander("Ver los 50 distritos"):
            st.dataframe(
                censo.rename(
                    columns={
                        "ubigeo": "Ubigeo",
                        "distrito": "Distrito",
                        "poblacion": "Población",
                        "hombres_18_34": "Hombres 18-34",
                        "mujeres_18_34": "Mujeres 18-34",
                        "porcentaje_hombres_18_34": "% hombres 18-34",
                    }
                ),
                hide_index=True,
                alt="Población joven por distrito de Lima y Callao",
            )

    with st.expander("Ver la tabla completa de la ENAHO"):
        st.dataframe(
            enaho.rename(
                columns={
                    "tabla": "Tabla",
                    "segmento": "Segmento",
                    "gasto_ropa_mes": "Gasto en ropa (S/ al mes)",
                    "porcentaje_del_gasto": "% del gasto del hogar",
                    "hogares": "Hogares",
                    "hogares_en_muestra": "Hogares en la muestra",
                }
            ),
            hide_index=True,
            alt="Gasto en vestido y calzado según la ENAHO 2025",
        )

    st.caption(
        "Fuentes: INEI, ENAHO 2025 (módulos 34 y 02), promedios ponderados con el factor de expansión; e INEI, "
        "Censos Nacionales 2025, consultado en REDATAM con el servidor MCP del proyecto (mcp/censo2025.py). "
        "La ENAHO no es representativa por distrito; por eso los distritos salen del censo."
    )

# ---------------------------------------------------------------------------
# 5. Tendencias y competencia (Claude con búsqueda web)
# ---------------------------------------------------------------------------
with pestana_tendencias:
    st.markdown(
        f"Claude busca en internet qué se está moviendo en redes para **{rubro}** "
        f"en el Perú y qué tiendas online te hacen competencia."
    )

    if st.button(
        "Buscar tendencias y competencia en vivo",
        icon=":material/travel_explore:",
        type="primary",
        disabled=not hay_clave,
        help=None if hay_clave else "Necesita una clave de API de Anthropic.",
    ):
        with st.spinner("Buscando en internet... toma uno o dos minutos."):
            st.session_state["tendencias"] = tendencias_guardadas(rubro, ciudad)

    resultado = st.session_state["tendencias"]
    if resultado:
        with st.container(border=True):
            st.markdown(resultado["texto"])
        if resultado["fuentes"]:
            with st.expander(f"Fuentes ({len(resultado['fuentes'])})"):
                for fuente in resultado["fuentes"]:
                    st.markdown(f"- [{fuente['titulo']}]({fuente['url']})")
    elif ARCHIVO_EJEMPLO_TENDENCIAS.exists():
        st.warning(
            "Este es un **ejemplo guardado**, no una búsqueda en vivo. Lo preparó Claude (con búsqueda "
            "web) el 11 de noviembre de 2026 para una tienda de streetwear en Lima. Con una clave de API, "
            "la app hace esta búsqueda en vivo para cualquier rubro y ciudad.",
            title="Ejemplo guardado",
            icon=":material/inventory_2:",
        )
        with st.container(border=True):
            st.markdown(ARCHIVO_EJEMPLO_TENDENCIAS.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# 6. Plan de la semana
# ---------------------------------------------------------------------------
with pestana_plan:
    if efectos is None or faltantes:
        st.info("El plan se activa cuando haya datos suficientes.", icon=":material/hourglass_top:")
    else:
        proximos = modelo.eventos_proximos(calendario, inicio_semana)
        fin_semana = inicio_semana + pd.Timedelta(days=6)
        st.markdown(
            f"Plan para la semana del **{inicio_semana:%d/%m}** al **{fin_semana:%d/%m/%Y}**, armado con "
            "tus números y los resultados del modelo."
        )

        if len(proximos) > 0:
            with st.expander("Lo que viene en el calendario (próximas 6 semanas)"):
                st.dataframe(
                    proximos.rename(
                        columns={"evento": "Evento", "tipo": "Tipo", "inicio": "Desde", "fin": "Hasta"}
                    ),
                    hide_index=True,
                    alt="Eventos próximos del calendario",
                )

        version = st.segmented_control(
            "Versión del plan",
            options=["Con reglas (gratis)", "Con Claude (IA)"],
            default="Con reglas (gratis)",
            required=True,
        )

        if version == "Con reglas (gratis)":
            plan = plan_reglas.armar_plan_con_reglas(ventas, efectos, proximos, inicio_semana)
            mostrar_plan(plan, "reglas")
        else:
            if not hay_clave:
                st.info(
                    "Para la versión con IA falta la clave de API de Anthropic. Agrégala en el archivo "
                    "`.env` (local) o en *Secrets* (Streamlit Cloud).",
                    icon=":material/key:",
                )
            if st.button(
                "Armar plan con Claude",
                icon=":material/auto_awesome:",
                type="primary",
                disabled=not hay_clave,
            ):
                resumen_tienda = (
                    analisis.resumen_en_texto(ventas, efecto)
                    + "\n\n"
                    + modelo.efectos_en_texto(efectos)
                    + "\n\nPróximos eventos del calendario:\n"
                    + proximos.to_string(index=False)
                )
                texto_tendencias = ""
                if st.session_state["tendencias"]:
                    texto_tendencias = st.session_state["tendencias"]["texto"]
                elif ARCHIVO_EJEMPLO_TENDENCIAS.exists():
                    texto_tendencias = ARCHIVO_EJEMPLO_TENDENCIAS.read_text(encoding="utf-8")
                with st.spinner("Armando tu plan..."):
                    st.session_state["plan_claude"] = plan_de_claude(rubro, resumen_tienda, texto_tendencias)

            plan = st.session_state["plan_claude"]
            if plan:
                mostrar_plan(plan, "claude")
            elif plan == {}:
                st.error("Claude no pudo armar el plan esta vez. Vuelve a intentarlo.")
