"""Genera datos sintéticos de una tienda de streetwear masculino.

Los datos son inventados, pero imitan lo que contó el dueño de una tienda
real en la entrevista 1 (docs/research/entrevista-01.md): vende por tienda
física, web, WhatsApp, Instagram, Facebook y lives, y liquida temporadas
pasadas con 40% de descuento.

Dentro de los datos hay un patrón escondido a propósito: los reels y los
lives empujan más ventas que las fotos. La app tiene que encontrarlo.

Uso:
    uv run python scripts/generar_datos.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Semilla fija: así cualquiera que corra el script obtiene los mismos datos.
azar = random.Random(20261110)

carpeta_datos = Path(__file__).parent.parent / "datos"
carpeta_datos.mkdir(exist_ok=True)

fecha_inicio = date(2026, 8, 1)
fecha_fin = date(2026, 10, 31)

# producto, categoría, precio de lista en soles, temporada, ventas base por día
productos = [
    ("Polera oversize negra", "Poleras", 89, "actual", 2.0),
    ("Polera estampada gráfica", "Poleras", 99, "actual", 1.6),
    ("Hoodie básico gris", "Hoodies", 189, "actual", 1.2),
    ("Hoodie colaboración edición limitada", "Hoodies", 349, "actual", 0.5),
    ("Pantalón cargo beige", "Pantalones", 169, "actual", 0.9),
    ("Zapatillas retro edición pasada", "Zapatillas", 459, "pasada", 0.4),
    ("Zapatillas skate blancas", "Zapatillas", 389, "actual", 0.7),
    ("Gorra bordada", "Accesorios", 79, "actual", 1.1),
    ("Casaca rompevientos temporada pasada", "Casacas", 259, "pasada", 0.3),
    ("Medias pack x3", "Accesorios", 45, "actual", 1.4),
]

canales = ["Tienda física", "Web", "WhatsApp", "Instagram", "Facebook", "Live"]
peso_canales = [0.30, 0.20, 0.20, 0.15, 0.07, 0.08]

# Cuánto multiplica cada formato las ventas del producto en los 3 días siguientes.
efecto_por_formato = {
    "Reel": 2.2,
    "Live": 2.6,
    "Carrusel": 1.4,
    "Foto": 1.1,
    "Historia": 1.2,
}
redes_por_formato = {
    "Reel": ["Instagram", "TikTok"],
    "Live": ["Instagram", "Facebook", "TikTok"],
    "Carrusel": ["Instagram", "Facebook"],
    "Foto": ["Instagram", "Facebook"],
    "Historia": ["Instagram", "WhatsApp"],
}

# ---------------------------------------------------------------------------
# 1. Publicaciones: unas 4 por semana
# ---------------------------------------------------------------------------
lista_publicaciones = []
dia = fecha_inicio
while dia <= fecha_fin:
    if azar.random() < 0.55:
        formato = azar.choice(list(efecto_por_formato))
        red = azar.choice(redes_por_formato[formato])
        producto = azar.choice(productos)
        # Los formatos que venden más también llegan a más gente, pero con ruido.
        alcance = int(azar.gauss(1500, 400) * efecto_por_formato[formato])
        alcance = max(alcance, 200)
        interacciones = int(alcance * azar.uniform(0.03, 0.09))
        lista_publicaciones.append(
            {
                "fecha": dia.isoformat(),
                "red": red,
                "formato": formato,
                "producto": producto[0],
                "alcance": alcance,
                "interacciones": interacciones,
            }
        )
    dia = dia + timedelta(days=1)

publicaciones = pd.DataFrame(lista_publicaciones)

# ---------------------------------------------------------------------------
# 2. Ventas: cada día, cada producto vende según su base y las publicaciones
# ---------------------------------------------------------------------------
lista_ventas = []
numero_pedido = 1001
dia = fecha_inicio
while dia <= fecha_fin:
    # Los sábados se vende más en tienda física, como en casi todo el retail.
    efecto_dia = 1.5 if dia.weekday() == 5 else 1.0

    for nombre, categoria, precio, temporada, base in productos:
        efecto_contenido = 1.0
        for publicacion in lista_publicaciones:
            dias_desde_post = (dia - date.fromisoformat(publicacion["fecha"])).days
            if publicacion["producto"] == nombre and 0 <= dias_desde_post <= 3:
                efecto_contenido = max(
                    efecto_contenido, efecto_por_formato[publicacion["formato"]]
                )

        esperado = base * efecto_dia * efecto_contenido
        unidades_del_dia = int(azar.gauss(esperado, esperado * 0.4) + 0.5)

        for _ in range(max(unidades_del_dia, 0)):
            descuento = 0.40 if temporada == "pasada" else 0.0
            lista_ventas.append(
                {
                    "fecha": dia.isoformat(),
                    "pedido": f"#{numero_pedido}",
                    "producto": nombre,
                    "categoria": categoria,
                    "temporada": temporada,
                    "canal": azar.choices(canales, peso_canales)[0],
                    "cantidad": 1,
                    "precio_lista": precio,
                    "descuento": descuento,
                    "total": round(precio * (1 - descuento), 2),
                }
            )
            numero_pedido = numero_pedido + 1
    dia = dia + timedelta(days=1)

ventas = pd.DataFrame(lista_ventas)

ventas.to_csv(carpeta_datos / "ventas_ejemplo.csv", index=False)
publicaciones.to_csv(carpeta_datos / "publicaciones_ejemplo.csv", index=False)

print(f"Ventas: {len(ventas)} filas")
print(f"Publicaciones: {len(publicaciones)} filas")
print(f"Guardado en {carpeta_datos}")
