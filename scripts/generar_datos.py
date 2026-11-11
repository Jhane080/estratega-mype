"""Genera los datos de ejemplo de una tienda de streetwear masculino en Lima.

Qué es real y qué es inventado:
- REAL: el calendario de eventos (datos/calendario_eventos.csv). Feriados,
  fechas comerciales, elecciones 2026, paros, la vacancia presidencial y la
  alerta de El Niño costero, con su fuente.
- INVENTADO: las ventas, las publicaciones y las promociones de la
  competencia. Imitan lo que contó el dueño de una tienda real en la
  entrevista 1 (docs/research/entrevista-01.md).

Dentro de las ventas hay patrones escondidos a propósito (los reels y los
lives venden más, la quincena sube las ventas, los paros las bajan...). El
modelo de la app tiene que encontrarlos por su cuenta.

Uso:
    uv run python scripts/generar_datos.py
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Semilla fija: así cualquiera que corra el script obtiene los mismos datos.
azar = np.random.default_rng(20261110)

carpeta_datos = Path(__file__).parent.parent / "datos"
carpeta_datos.mkdir(exist_ok=True)

fecha_inicio = date(2024, 11, 9)
fecha_fin = date(2026, 11, 8)
todas_las_fechas = pd.date_range(fecha_inicio, fecha_fin, freq="D")

# ---------------------------------------------------------------------------
# 1. Calendario de eventos REALES (con fuente)
# ---------------------------------------------------------------------------
FUENTE_FERIADOS = "Feriados nacionales del Perú (gob.pe)"
eventos = []


def agregar_evento(inicio, fin, nombre, tipo, fuente):
    dia = inicio
    while dia <= fin:
        eventos.append({"fecha": dia, "evento": nombre, "tipo": tipo, "fuente": fuente})
        dia = dia + timedelta(days=1)


feriados = [
    (date(2024, 12, 8), "Inmaculada Concepción"),
    (date(2024, 12, 9), "Batalla de Ayacucho"),
    (date(2024, 12, 25), "Navidad"),
    (date(2025, 1, 1), "Año Nuevo"),
    (date(2025, 4, 17), "Jueves Santo"),
    (date(2025, 4, 18), "Viernes Santo"),
    (date(2025, 5, 1), "Día del Trabajo"),
    (date(2025, 6, 7), "Batalla de Arica"),
    (date(2025, 6, 29), "San Pedro y San Pablo"),
    (date(2025, 7, 23), "Día de la Fuerza Aérea"),
    (date(2025, 7, 28), "Fiestas Patrias"),
    (date(2025, 7, 29), "Fiestas Patrias"),
    (date(2025, 8, 6), "Batalla de Junín"),
    (date(2025, 8, 30), "Santa Rosa de Lima"),
    (date(2025, 10, 8), "Combate de Angamos"),
    (date(2025, 11, 1), "Todos los Santos"),
    (date(2025, 12, 8), "Inmaculada Concepción"),
    (date(2025, 12, 9), "Batalla de Ayacucho"),
    (date(2025, 12, 25), "Navidad"),
    (date(2026, 1, 1), "Año Nuevo"),
    (date(2026, 4, 2), "Jueves Santo"),
    (date(2026, 4, 3), "Viernes Santo"),
    (date(2026, 5, 1), "Día del Trabajo"),
    (date(2026, 6, 7), "Batalla de Arica"),
    (date(2026, 6, 29), "San Pedro y San Pablo"),
    (date(2026, 7, 23), "Día de la Fuerza Aérea"),
    (date(2026, 7, 28), "Fiestas Patrias"),
    (date(2026, 7, 29), "Fiestas Patrias"),
    (date(2026, 8, 6), "Batalla de Junín"),
    (date(2026, 8, 30), "Santa Rosa de Lima"),
    (date(2026, 10, 8), "Combate de Angamos"),
    (date(2026, 11, 1), "Todos los Santos"),
    (date(2026, 12, 8), "Inmaculada Concepción"),
    (date(2026, 12, 9), "Batalla de Ayacucho"),
    (date(2026, 12, 25), "Navidad"),
]
for dia, nombre in feriados:
    agregar_evento(dia, dia, nombre, "feriado", FUENTE_FERIADOS)

# Fechas comerciales: se cuenta la semana previa, que es cuando la gente compra.
FUENTE_CYBER = "IAB Perú, ediciones de Cyber Wow (cyberwow.pe)"
agregar_evento(date(2024, 11, 25), date(2024, 11, 29), "Black Friday", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2024, 12, 15), date(2024, 12, 24), "Campaña navideña", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2025, 4, 7), date(2025, 4, 10), "Cyber Wow", "fecha_comercial", FUENTE_CYBER)
agregar_evento(date(2025, 5, 5), date(2025, 5, 11), "Día de la Madre", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2025, 6, 9), date(2025, 6, 15), "Día del Padre", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2025, 11, 3), date(2025, 11, 6), "Cyber Wow", "fecha_comercial", FUENTE_CYBER)
agregar_evento(date(2025, 11, 24), date(2025, 11, 28), "Black Friday", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2025, 12, 15), date(2025, 12, 24), "Campaña navideña", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2026, 4, 20), date(2026, 4, 23), "Cyber Wow", "fecha_comercial", FUENTE_CYBER)
agregar_evento(date(2026, 5, 4), date(2026, 5, 10), "Día de la Madre", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2026, 6, 15), date(2026, 6, 21), "Día del Padre", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2026, 7, 13), date(2026, 7, 16), "Cyber Wow", "fecha_comercial", FUENTE_CYBER)
agregar_evento(date(2026, 11, 2), date(2026, 11, 5), "Cyber Wow", "fecha_comercial", FUENTE_CYBER)
agregar_evento(date(2026, 11, 23), date(2026, 11, 27), "Black Friday", "fecha_comercial", "Calendario comercial")
agregar_evento(date(2026, 12, 15), date(2026, 12, 24), "Campaña navideña", "fecha_comercial", "Calendario comercial")

# Elecciones generales 2026: se cuentan las 4 semanas previas a cada vuelta.
FUENTE_JNE = "JNE: primera vuelta 12/04/2026, segunda vuelta 07/06/2026"
agregar_evento(date(2026, 3, 16), date(2026, 4, 12), "Campaña electoral, primera vuelta", "periodo_electoral", FUENTE_JNE)
agregar_evento(date(2026, 5, 11), date(2026, 6, 7), "Campaña electoral, segunda vuelta", "periodo_electoral", FUENTE_JNE)

# Paros y crisis política en Lima.
agregar_evento(date(2025, 10, 2), date(2025, 10, 2), "Paro de transportistas", "crisis_o_paro", "Prensa: La República, 02/10/2025")
agregar_evento(date(2025, 10, 4), date(2025, 10, 5), "Marcha nacional Generación Z", "crisis_o_paro", "Prensa: El Búho, 04/10/2025")
agregar_evento(date(2025, 10, 6), date(2025, 10, 7), "Paro de transportistas", "crisis_o_paro", "Prensa: Infobae, 06/10/2025")
agregar_evento(date(2025, 10, 10), date(2025, 10, 12), "Vacancia presidencial", "crisis_o_paro", "Congreso de la República, 10/10/2025")
agregar_evento(date(2025, 10, 15), date(2025, 10, 15), "Paro y marcha nacional", "crisis_o_paro", "Prensa: El Ciudadano, 13/10/2025")

# El Niño costero: el ENFEN pasa a "vigilancia" el 15/01/2026 y luego a "alerta".
agregar_evento(date(2026, 1, 15), date(2026, 12, 31), "El Niño costero (vigilancia o alerta)", "alerta_fen", "ENFEN, Comunicado Oficial N.° 01-2026 y siguientes")

calendario = pd.DataFrame(eventos)
calendario.to_csv(carpeta_datos / "calendario_eventos.csv", index=False)

# Indicadores por día (sí o no) para generar las ventas.
indicadores = pd.DataFrame(index=todas_las_fechas)
for tipo in ["feriado", "fecha_comercial", "periodo_electoral", "crisis_o_paro", "alerta_fen"]:
    fechas_del_tipo = pd.to_datetime(calendario.loc[calendario["tipo"] == tipo, "fecha"])
    indicadores[tipo] = indicadores.index.isin(fechas_del_tipo)

# ---------------------------------------------------------------------------
# 2. Competencia (INVENTADO): días en que un competidor lanzó una promoción
# ---------------------------------------------------------------------------
competencia = pd.DataFrame(
    {"fecha": todas_las_fechas.date, "promo_competencia": azar.random(len(todas_las_fechas)) < 0.18}
)
competencia.to_csv(carpeta_datos / "competencia_ejemplo.csv", index=False)
indicadores["promo_competencia"] = competencia["promo_competencia"].to_numpy()

# ---------------------------------------------------------------------------
# 3. Productos y publicaciones (INVENTADO)
# ---------------------------------------------------------------------------
# producto, categoría, precio de lista en soles, temporada, ventas base por día
productos = [
    ("Polera oversize negra", "Poleras", 89, "actual", 1.6),
    ("Polera estampada gráfica", "Poleras", 99, "actual", 1.3),
    ("Hoodie básico gris", "Hoodies", 189, "actual", 0.9),
    ("Hoodie colaboración edición limitada", "Hoodies", 349, "actual", 0.35),
    ("Pantalón cargo beige", "Pantalones", 169, "actual", 0.7),
    ("Zapatillas retro edición pasada", "Zapatillas", 459, "pasada", 0.3),
    ("Zapatillas skate blancas", "Zapatillas", 389, "actual", 0.5),
    ("Gorra bordada", "Accesorios", 79, "actual", 0.9),
    ("Casaca rompevientos temporada pasada", "Casacas", 259, "pasada", 0.25),
    ("Medias pack x3", "Accesorios", 45, "actual", 1.1),
]
nombres_productos = [producto[0] for producto in productos]

# Cuánto multiplica cada formato las ventas del producto en los 3 días siguientes.
efecto_por_formato = {"Reel": 2.0, "Live": 2.4, "Carrusel": 1.3, "Foto": 1.05, "Historia": 1.15}
redes_por_formato = {
    "Reel": ["Instagram", "TikTok"],
    "Live": ["Instagram", "Facebook", "TikTok"],
    "Carrusel": ["Instagram", "Facebook"],
    "Foto": ["Instagram", "Facebook"],
    "Historia": ["Instagram", "WhatsApp"],
}
formatos = list(efecto_por_formato)

lista_publicaciones = []
for fecha in todas_las_fechas:
    if azar.random() < 0.55:
        formato = formatos[azar.integers(len(formatos))]
        redes = redes_por_formato[formato]
        red = redes[azar.integers(len(redes))]
        producto = nombres_productos[azar.integers(len(nombres_productos))]
        alcance = max(int(azar.normal(1500, 400) * efecto_por_formato[formato]), 200)
        lista_publicaciones.append(
            {
                "fecha": fecha.date(),
                "red": red,
                "formato": formato,
                "producto": producto,
                "alcance": alcance,
                "interacciones": int(alcance * azar.uniform(0.03, 0.09)),
            }
        )
publicaciones = pd.DataFrame(lista_publicaciones)
publicaciones.to_csv(carpeta_datos / "publicaciones_ejemplo.csv", index=False)

# Efecto de contenido por producto y día: el mayor de los posts de los 3 días previos.
efecto_contenido = pd.DataFrame(1.0, index=todas_las_fechas, columns=nombres_productos)
for publicacion in lista_publicaciones:
    inicio = pd.Timestamp(publicacion["fecha"])
    fin = inicio + pd.Timedelta(days=3)
    ventana = efecto_contenido.loc[inicio:fin, publicacion["producto"]]
    efecto_contenido.loc[inicio:fin, publicacion["producto"]] = ventana.clip(
        lower=efecto_por_formato[publicacion["formato"]]
    )

# Descuentos relámpago (INVENTADO): cada producto de temporada actual tiene
# algunas semanas al año con 20% de descuento.
descuentos = pd.DataFrame(0.0, index=todas_las_fechas, columns=nombres_productos)
for nombre, categoria, precio, temporada, base in productos:
    if temporada == "pasada":
        descuentos[nombre] = 0.40
    else:
        for _ in range(5):
            inicio = todas_las_fechas[azar.integers(len(todas_las_fechas) - 7)]
            descuentos.loc[inicio : inicio + pd.Timedelta(days=6), nombre] = 0.20

# ---------------------------------------------------------------------------
# 4. Ventas (INVENTADO), con los patrones escondidos
# ---------------------------------------------------------------------------
efecto_dia_semana = {0: 0.85, 1: 0.9, 2: 0.95, 3: 1.0, 4: 1.15, 5: 1.5, 6: 1.2}
canales = ["Tienda física", "Web", "WhatsApp", "Instagram", "Facebook", "Live"]
peso_canales = [0.30, 0.20, 0.20, 0.15, 0.07, 0.08]

lista_ventas = []
numero_pedido = 1001
for numero_dia, fecha in enumerate(todas_las_fechas):
    dia = indicadores.loc[fecha]
    es_quincena = fecha.day in (1, 15, 16, 30, 31)

    multiplicador_del_dia = efecto_dia_semana[fecha.day_of_week]
    multiplicador_del_dia = multiplicador_del_dia * (1 + 0.10 * numero_dia / 365)  # crece 10% al año
    if es_quincena:
        multiplicador_del_dia = multiplicador_del_dia * 1.25
    if dia["feriado"]:
        multiplicador_del_dia = multiplicador_del_dia * 1.10
    if dia["fecha_comercial"]:
        multiplicador_del_dia = multiplicador_del_dia * 1.70
    if dia["periodo_electoral"]:
        multiplicador_del_dia = multiplicador_del_dia * 0.85
    if dia["crisis_o_paro"]:
        multiplicador_del_dia = multiplicador_del_dia * 0.55
    if dia["alerta_fen"]:
        multiplicador_del_dia = multiplicador_del_dia * 0.95
    if dia["promo_competencia"]:
        multiplicador_del_dia = multiplicador_del_dia * 0.88

    for nombre, categoria, precio, temporada, base in productos:
        descuento = descuentos.loc[fecha, nombre]
        esperado = base * multiplicador_del_dia * efecto_contenido.loc[fecha, nombre]
        if temporada == "actual" and descuento > 0:
            esperado = esperado * 1.40
        unidades_del_dia = azar.poisson(esperado)

        for _ in range(unidades_del_dia):
            canal = canales[azar.choice(len(canales), p=peso_canales)]
            lista_ventas.append(
                {
                    "fecha": fecha.date(),
                    "pedido": f"#{numero_pedido}",
                    "producto": nombre,
                    "categoria": categoria,
                    "temporada": temporada,
                    "canal": canal,
                    "cantidad": 1,
                    "precio_lista": precio,
                    "descuento": descuento,
                    "total": round(precio * (1 - descuento), 2),
                }
            )
            numero_pedido = numero_pedido + 1

ventas = pd.DataFrame(lista_ventas)
ventas.to_csv(carpeta_datos / "ventas_ejemplo.csv", index=False)

print(f"Ventas: {len(ventas)} filas")
print(f"Publicaciones: {len(publicaciones)} filas")
print(f"Eventos del calendario: {len(calendario)} filas")
print(f"Guardado en {carpeta_datos}")
