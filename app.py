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

if "tendencias" not in st.session_state:
    st.session_state["tendencias"] = None
if "plan" not in st.session_state:
    st.session_state["plan"] = None


# Las llamadas a Claude cuestan plata. Se guardan 6 horas: si se pide lo mismo
# otra vez (por ejemplo, en el ensayo y en la presentación), no se paga dos veces.
@st.cache_data(ttl="6h", show_spinner=False)
def tendencias_guardadas(rubro: str, ciudad: str) -> dict:
    return ia.buscar_tendencias(ia.crear_cliente(), rubro, ciudad)


@st.cache_data(ttl="6h", show_spinner=False)
def plan_guardado(rubro: str, resumen_tienda: str, tendencias: str) -> dict:
    return ia.armar_plan(ia.crear_cliente(), rubro, resumen_tienda, tendencias)


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
        st.caption("Descarga los ejemplos para ver qué columnas necesita cada archivo.")
        st.download_button(
            "Ejemplo de ventas",
            data=(CARPETA_DATOS / "ventas_ejemplo.csv").read_bytes(),
            file_name="ventas_ejemplo.csv",
            icon=":material/download:",
        )
        st.download_button(
            "Ejemplo de publicaciones",
            data=(CARPETA_DATOS / "publicaciones_ejemplo.csv").read_bytes(),
            file_name="publicaciones_ejemplo.csv",
            icon=":material/download:",
        )
    else:
        archivo_ventas = CARPETA_DATOS / "ventas_ejemplo.csv"
        archivo_publicaciones = CARPETA_DATOS / "publicaciones_ejemplo.csv"
        st.caption(
            "Datos inventados de una tienda de streetwear, armados a partir de una "
            "entrevista real con su dueño."
        )

st.title("Estratega MYPE")
st.caption("Tu analista de marketing: qué vender, qué promocionar y qué publicar la próxima semana.")

if archivo_ventas is None or archivo_publicaciones is None:
    st.info("Sube tus dos archivos en la barra lateral para empezar.", icon=":material/upload_file:")
    st.stop()

ventas = analisis.leer_ventas(archivo_ventas)
publicaciones = analisis.leer_publicaciones(archivo_publicaciones)
efecto = analisis.efecto_de_cada_publicacion(ventas, publicaciones)

# Antes de recomendar nada, revisamos si hay datos suficientes.
faltantes = analisis.revisar_si_hay_datos_suficientes(ventas, publicaciones)
if faltantes:
    st.warning(
        "\n".join(f"- {faltante}" for faltante in faltantes)
        + "\n\nPuedes ver tus números, pero el plan se activa cuando haya datos suficientes.",
        title="Todavía faltan datos para recomendar",
        icon=":material/hourglass_top:",
    )

pestana_ventas, pestana_contenido, pestana_tendencias, pestana_plan = st.tabs(
    [
        ":material/payments: Ventas",
        ":material/movie: Contenido que vende",
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

    with st.container(horizontal=True):
        st.metric("Ventas", f"S/ {total_soles:,.0f}", border=True)
        st.metric("Pedidos", f"{total_pedidos:,}", border=True)
        st.metric("Ticket promedio", f"S/ {total_soles / total_pedidos:,.0f}", border=True)
        st.metric("Producto estrella", producto_estrella, border=True)

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

    with st.container(border=True):
        st.subheader("Qué día se vende más")
        st.caption("Venta promedio de cada día de la semana.")
        st.bar_chart(
            analisis.ventas_por_dia_semana(ventas),
            x="dia_semana",
            y="soles_promedio",
            sort=False,
            x_label="",
            y_label="Soles por día",
            alt="Venta promedio por día de la semana",
        )

# ---------------------------------------------------------------------------
# 2. Contenido que vende
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
# 3. Tendencias y competencia (Claude con búsqueda web)
# ---------------------------------------------------------------------------
with pestana_tendencias:
    st.markdown(
        f"Claude busca en internet qué se está moviendo en redes para **{rubro}** "
        f"en el Perú y qué tiendas online te hacen competencia."
    )

    if not hay_clave:
        st.info(
            "Falta la clave de API de Anthropic. Agrégala en el archivo `.env` (local) "
            "o en *Secrets* (Streamlit Cloud).",
            icon=":material/key:",
        )

    if st.button(
        "Buscar tendencias y competencia",
        icon=":material/travel_explore:",
        type="primary",
        disabled=not hay_clave,
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

# ---------------------------------------------------------------------------
# 4. Plan de la semana (Claude con salidas estructuradas)
# ---------------------------------------------------------------------------
with pestana_plan:
    st.markdown(
        "Claude junta tus números, el contenido que te funciona y las tendencias, "
        "y te propone qué hacer la próxima semana."
    )
    if st.session_state["tendencias"] is None:
        st.caption("Tip: busca primero las tendencias para que el plan las tome en cuenta.")

    if st.button(
        "Armar plan de la semana",
        icon=":material/auto_awesome:",
        type="primary",
        disabled=(not hay_clave) or bool(faltantes),
    ):
        resumen_tienda = analisis.resumen_en_texto(ventas, efecto)
        texto_tendencias = ""
        if st.session_state["tendencias"]:
            texto_tendencias = st.session_state["tendencias"]["texto"]
        with st.spinner("Armando tu plan..."):
            st.session_state["plan"] = plan_guardado(rubro, resumen_tienda, texto_tendencias)

    plan = st.session_state["plan"]
    if plan:
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
        calendario = pd.DataFrame(plan["contenido"]).rename(
            columns={"dia": "Día", "red": "Red", "formato": "Formato", "producto": "Producto", "idea": "Idea"}
        )
        st.dataframe(calendario, hide_index=True, alt="Calendario de contenido de la semana")
        st.download_button(
            "Descargar calendario",
            data=calendario.to_csv(index=False).encode("utf-8"),
            file_name="calendario_contenido.csv",
            icon=":material/download:",
        )

        st.subheader(":material/block: Qué dejar de hacer")
        for consejo in plan["que_evitar"]:
            st.markdown(f"- {consejo}")
    elif plan == {}:
        st.error("Claude no pudo armar el plan esta vez. Vuelve a intentarlo.")
