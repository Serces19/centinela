#!/usr/bin/env python3
"""
Centinela · Hackathon Business AI School
Generador del dataset sintético de "Distribuidora Andina S.A.S." (empresa ficticia).

12 meses de operación (2025-10-01 a 2026-09-30): clientes, productos, proveedores,
listas de precios, costos, órdenes de compra, pedidos, facturas, pagos e inventario diario.
Incluye escenarios de negocio "sembrados" para probar a los agentes.

Uso:
    python generar_dataset.py                 # semilla por defecto
    SEMILLA=123 python generar_dataset.py     # otra semilla = otras entidades afectadas
Salida: carpeta ./csv
"""
import os
import numpy as np
import pandas as pd

SEMILLA = int(os.environ.get("SEMILLA", "7"))
SALIDA = os.environ.get("SALIDA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv"))
rng = np.random.default_rng(SEMILLA)

INICIO, FIN = pd.Timestamp("2025-10-01"), pd.Timestamp("2026-09-30")
DIAS = pd.date_range(INICIO, FIN, freq="D")
N_PEDIDOS_OBJETIVO = 20000

# ----------------------------------------------------------------------------------------
# Maestros
# ----------------------------------------------------------------------------------------
CIUDADES = {  # ciudad: (región, bodega que la atiende, peso)
    "Bogotá": ("Centro", "BOD-BOG", 0.28), "Medellín": ("Antioquia y Eje Cafetero", "BOD-MDE", 0.24),
    "Cali": ("Occidente", "BOD-BOG", 0.14), "Barranquilla": ("Caribe", "BOD-MDE", 0.12),
    "Bucaramanga": ("Oriente", "BOD-BOG", 0.08), "Pereira": ("Antioquia y Eje Cafetero", "BOD-MDE", 0.07),
    "Cartagena": ("Caribe", "BOD-MDE", 0.07),
}
BODEGAS = pd.DataFrame([
    {"bodega_id": "BOD-MDE", "nombre": "Bodega Medellín (Itagüí)", "ciudad": "Medellín"},
    {"bodega_id": "BOD-BOG", "nombre": "Bodega Bogotá (Funza)", "ciudad": "Bogotá"},
])
SEGMENTOS = {  # segmento: (peso, pedidos/mes, unidades por línea, plazo días, tope descuento %)
    "Grandes superficies": (0.04, 12.0, 60, 60, 18),
    "Mayoristas": (0.18, 8.0, 30, 45, 15),
    "Minoristas": (0.63, 2.5, 6, 30, 10),
    "Institucional": (0.15, 3.0, 15, 45, 12),
}
NOMBRES_V = ["Andrés Gómez", "Carolina Restrepo", "Juan Pablo Ríos", "Natalia Vélez", "Santiago Muñoz",
             "Laura Cárdenas", "Felipe Ospina", "Daniela Rojas", "Camilo Herrera", "Valentina Arango",
             "Sebastián Castro", "Mariana López", "Julián Pérez", "Paula Jaramillo", "Diego Morales",
             "Catalina Zapata", "Esteban Salazar", "Manuela Torres", "Alejandro Quintero", "Isabela Mejía",
             "Mateo Giraldo", "Sara Montoya", "Nicolás Duque", "Luisa Fernanda Ruiz", "Tomás Betancur"]
REG_VEND = (["Antioquia y Eje Cafetero"] * 6 + ["Centro"] * 7 + ["Occidente"] * 4 + ["Caribe"] * 5 + ["Oriente"] * 3)
rng.shuffle(REG_VEND)
vendedores = pd.DataFrame({"vendedor_id": [f"V{i+1:02d}" for i in range(25)], "nombre": NOMBRES_V, "region": REG_VEND})

# Clientes
PREF = ["Distribuciones", "Comercializadora", "Almacenes", "Supermercado", "Droguería", "Ferretería",
        "Inversiones", "Mercados", "Tiendas", "Grupo"]
CORE = ["El Roble", "La Montaña", "Andina", "del Valle", "Caribe", "San José", "La Esperanza", "Los Andes",
        "Central", "Santa Fe", "El Prado", "La 70", "Boyacá", "Del Norte", "Primavera", "Monserrate",
        "La Sabana", "El Poblado", "Laureles", "La Candelaria"]
SUF = ["", " Express", " Plus", " & Cía", " Hermanos", " del Sur", " Mayorista"]
combos = [f"{p} {c}{s} S.A.S." for p in PREF for c in CORE for s in SUF]
nombres_c = list(rng.choice(combos, size=500, replace=False))
ciudades = list(CIUDADES)
pc = np.array([CIUDADES[c][2] for c in ciudades]); pc = pc / pc.sum()
segs = list(SEGMENTOS)
ps = np.array([SEGMENTOS[s][0] for s in segs]); ps = ps / ps.sum()
cli_ciudad = rng.choice(ciudades, size=500, p=pc)
cli_seg = rng.choice(segs, size=500, p=ps)
cli_vend = []
for c in cli_ciudad:
    reg = CIUDADES[c][0]
    cli_vend.append(rng.choice(vendedores.loc[vendedores.region == reg, "vendedor_id"].values))
tam = rng.lognormal(0, 0.55, size=500)
clientes = pd.DataFrame({
    "cliente_id": [f"C{i+1:04d}" for i in range(500)], "nombre": nombres_c, "segmento": cli_seg,
    "ciudad": cli_ciudad, "region": [CIUDADES[c][0] for c in cli_ciudad], "vendedor_id": cli_vend,
    "plazo_dias": [SEGMENTOS[s][3] for s in cli_seg],
    "fecha_alta": [pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(d)) for d in rng.integers(0, 2700, 500)],
})
clientes["_tam"] = tam

# Proveedores
PROV_NOM = ["Industrias Plásticas del Valle", "Químicos Andinos", "Alimentos La Sabana", "Bebidas del Caribe",
            "Cosméticos Primavera", "Papeles Monserrate", "Nutrición Animal Andina", "Hogar Total Importaciones",
            "Limpieza Profesional", "Lácteos del Norte", "Granos de Colombia", "Envases Medellín",
            "Distribuidora de Aseo Central", "Café y Cacao del Huila", "Pastas Doria Sur", "Aguas del Oriente",
            "Higiene y Cuidado SAS", "Mascotas Felices SAS", "Útiles Escolares Andes", "Textiles del Hogar",
            "Snacks y Pasabocas", "Conservas del Pacífico", "Jugos Tropicales", "Detergentes Unidos",
            "Cerámicas y Menaje", "Aceites Vegetales", "Harinas del Valle", "Dulces Antioqueños",
            "Electro Hogar Import", "Bolsas y Empaques", "Vidrios Andinos", "Galletas del Norte",
            "Carnes Frías Caribe", "Salsas y Condimentos", "Cuidado Bebé SAS", "Farmacéutica Andina",
            "Oficina Total", "Insecticidas del Campo", "Velas y Aromas", "Cuidado Capilar SAS"]
proveedores = pd.DataFrame({"proveedor_id": [f"PR{i+1:02d}" for i in range(40)], "nombre": PROV_NOM,
                            "lead_time_dias": rng.integers(5, 10, 40), "pais": ["Colombia"] * 34 + ["China", "México", "Perú", "Ecuador", "Brasil", "Chile"]})

LINEAS = {  # línea: (n SKU, costo min, costo max, margen objetivo, proveedores, artículos)
    "Hogar": (30, 8000, 60000, 0.32, ["PR08", "PR20", "PR25", "PR29", "PR31"],
              ["Juego de ollas", "Sartén antiadherente", "Toalla de baño", "Juego de sábanas", "Recipiente hermético",
               "Escoba", "Trapero", "Organizador plástico", "Vaso de vidrio x6", "Cuchillo de cocina"]),
    "Aseo": (35, 3000, 25000, 0.28, ["PR02", "PR09", "PR13", "PR24", "PR38"],
             ["Detergente en polvo", "Lavaloza líquido", "Limpiador multiusos", "Blanqueador", "Suavizante",
              "Desinfectante", "Jabón de barra", "Ambientador", "Esponja", "Bolsas de basura"]),
    "Alimentos": (45, 2000, 20000, 0.22, ["PR03", "PR10", "PR11", "PR15", "PR22", "PR26", "PR27", "PR28", "PR32", "PR34"],
                  ["Arroz", "Aceite", "Pasta", "Atún", "Café molido", "Chocolate de mesa", "Galletas", "Leche en polvo",
                   "Harina de maíz", "Salsa de tomate", "Lentejas", "Azúcar"]),
    "Bebidas": (35, 1500, 12000, 0.25, ["PR04", "PR16", "PR23"],
                ["Gaseosa", "Agua sin gas", "Jugo de naranja", "Bebida energizante", "Té helado", "Malta",
                 "Agua con gas", "Bebida isotónica"]),
    "Cuidado personal": (30, 4000, 30000, 0.35, ["PR05", "PR17", "PR35", "PR40"],
                         ["Shampoo", "Crema dental", "Desodorante", "Jabón líquido", "Crema corporal", "Pañales",
                          "Toallas higiénicas", "Protector solar"]),
    "Mascotas": (15, 10000, 90000, 0.30, ["PR07", "PR18"],
                 ["Concentrado perro adulto", "Concentrado gato", "Snack para perro", "Arena para gato", "Shampoo para mascotas"]),
    "Papelería": (10, 1000, 15000, 0.38, ["PR06", "PR19", "PR37"],
                  ["Cuaderno", "Resma de papel", "Bolígrafos x12", "Marcadores", "Carpeta"]),
}
PRESENT = ["x1", "x3", "x6", "x12", "250 g", "500 g", "1 kg", "2 kg", "400 ml", "1 L", "1.5 L", "3 L"]
rows = []
k = 0
for linea, (n, cmin, cmax, mg, provs, arts) in LINEAS.items():
    for j in range(n):
        k += 1
        costo = float(np.exp(rng.uniform(np.log(cmin), np.log(cmax))))
        m = float(np.clip(rng.normal(mg, 0.03), 0.12, 0.5))
        rows.append({"sku": f"P{k:04d}", "nombre": f"{arts[j % len(arts)]} {PRESENT[rng.integers(0, len(PRESENT))]} ({linea[:3].upper()}-{j+1:02d})",
                     "linea": linea, "proveedor_id": provs[j % len(provs)], "_costo0": round(costo, -1),
                     "_margen": m, "_pop": float(rng.lognormal(0, 0.9))})
productos = pd.DataFrame(rows)

# ----------------------------------------------------------------------------------------
# Selección de entidades de los escenarios (depende de la semilla)
# ----------------------------------------------------------------------------------------
hogar = productos[productos.linea == "Hogar"].sort_values("_pop", ascending=False)
S1_PROV = "PR08"
s1_cand = hogar[hogar.proveedor_id == S1_PROV].index[:4]
productos.loc[s1_cand, "_pop"] *= 2.2          # artículos relevantes de la línea
S1_SKUS = list(productos.loc[s1_cand, "sku"])
S1_FECHA = pd.Timestamp("2026-08-15"); S1_ALZA = 1.25

beb = productos[productos.linea == "Bebidas"].sort_values("_pop", ascending=False)
S3_SKU = beb.iloc[0]["sku"]; productos.loc[beb.index[0], "_pop"] *= 1.6
S3_BOD = "BOD-MDE"

# Cliente con mora creciente: mayorista grande, plazo 30
may = clientes[clientes.segmento == "Mayoristas"].sample(2, random_state=SEMILLA).index
S2_CLI = clientes.loc[may[0], "cliente_id"]
clientes.loc[may[0], ["_tam", "plazo_dias"]] = [4.5, 30]
# Cliente que se va: mayorista estable
S5_CLI = clientes.loc[may[1], "cliente_id"]
clientes.loc[may[1], "_tam"] = 1.6
S5_FIN = pd.Timestamp("2026-07-20")

# Vendedor con descuentos fuera de política (región Caribe)
S4_VEND = vendedores.loc[vendedores.region == "Caribe", "vendedor_id"].iloc[1]
S4_DESDE = pd.Timestamp("2026-07-01")


# ----------------------------------------------------------------------------------------
# Listas de precios y costos de proveedor (vigencias)
# ----------------------------------------------------------------------------------------
lp = []
for _, p in productos.iterrows():
    precio0 = round(p._costo0 / (1 - p._margen), -1)
    lp.append({"sku": p.sku, "fecha_vigencia": INICIO, "precio_lista": precio0})
    lp.append({"sku": p.sku, "fecha_vigencia": pd.Timestamp("2026-01-15"), "precio_lista": round(precio0 * 1.045, -1)})
lista_precios = pd.DataFrame(lp)

cp = []
meses = pd.date_range(INICIO, FIN, freq="MS")
for _, p in productos.iterrows():
    c = p._costo0
    for i, m in enumerate(meses):
        c = c * (1 + 0.0035 + rng.normal(0, 0.006)) if i > 0 else c
        cp.append({"sku": p.sku, "proveedor_id": p.proveedor_id, "fecha_vigencia": m, "costo_unitario": round(c, 0)})
costos = pd.DataFrame(cp)
# Escenario 1: alza del proveedor sin ajuste del precio de venta
for s in S1_SKUS:
    base = costos[(costos.sku == s) & (costos.fecha_vigencia <= S1_FECHA)].iloc[-1].costo_unitario
    costos.loc[(costos.sku == s) & (costos.fecha_vigencia > S1_FECHA), "costo_unitario"] = round(base * S1_ALZA * 1.003, 0)
    costos = pd.concat([costos, pd.DataFrame([{"sku": s, "proveedor_id": S1_PROV, "fecha_vigencia": S1_FECHA,
                                               "costo_unitario": round(base * S1_ALZA, 0)}])], ignore_index=True)
costos = costos.sort_values(["sku", "fecha_vigencia"]).reset_index(drop=True)

def vigente(tabla, valor, skus, fechas):
    """Valor vigente por SKU a cada fecha (merge_asof)."""
    q = pd.DataFrame({"sku": skus, "fecha": fechas, "_i": np.arange(len(skus))}).sort_values("fecha")
    t = tabla.sort_values("fecha_vigencia")
    r = pd.merge_asof(q, t[["sku", "fecha_vigencia", valor]], left_on="fecha", right_on="fecha_vigencia", by="sku")
    return r.sort_values("_i")[valor].values

# ----------------------------------------------------------------------------------------
# Pedidos
# ----------------------------------------------------------------------------------------
peso_dia = np.ones(len(DIAS))
peso_dia *= np.where(DIAS.dayofweek == 6, 0.08, np.where(DIAS.dayofweek == 5, 0.55, 1.0))
peso_dia *= np.where(DIAS.month == 12, 1.35, np.where(DIAS.month == 1, 0.85, 1.0))
peso_dia *= 1 + 0.04 * np.sin(np.arange(len(DIAS)) / 365 * 2 * np.pi)
peso_dia = peso_dia / peso_dia.sum()

tasa = np.array([SEGMENTOS[s][1] for s in clientes.segmento]) * clientes._tam.values
tasa = tasa / tasa.sum() * N_PEDIDOS_OBJETIVO
ped = []
for i, c in clientes.iterrows():
    if c.cliente_id == S5_CLI:
        d = INICIO + pd.Timedelta(days=2)
        while d < S5_FIN:
            ped.append((c.cliente_id, d)); d += pd.Timedelta(days=int(7 + rng.integers(-1, 2)))
        continue
    n = rng.poisson(tasa[i])
    for d in rng.choice(DIAS, size=n, p=peso_dia):
        ped.append((c.cliente_id, pd.Timestamp(d)))
pedidos = pd.DataFrame(ped, columns=["cliente_id", "fecha"]).sort_values(["fecha", "cliente_id"]).reset_index(drop=True)
pedidos["pedido_id"] = [f"PED-{i+1:06d}" for i in range(len(pedidos))]
pedidos = pedidos.merge(clientes[["cliente_id", "vendedor_id", "ciudad", "segmento"]], on="cliente_id")
pedidos["canal"] = rng.choice(["Asesor en campo", "Televenta", "Portal B2B"], size=len(pedidos), p=[0.55, 0.25, 0.20])
est = np.where(rng.random(len(pedidos)) < 0.04, "Cancelado", "Facturado")
ult = pedidos.fecha >= FIN - pd.Timedelta(days=3)
est = np.where(ult & (rng.random(len(pedidos)) < 0.65) & (est != "Cancelado"), "Pendiente de despacho", est)
pedidos["estado"] = est
pedidos = pedidos.sort_values("pedido_id").reset_index(drop=True)

# Líneas
pop = productos._pop.values / productos._pop.sum()
lin = []
for _, o in pedidos.iterrows():
    nl = min(1 + rng.poisson(2), 12)
    skus = rng.choice(productos.sku.values, size=nl, replace=False, p=pop)
    base_q = SEGMENTOS[o.segmento][2]
    for s in skus:
        q = max(1, int(round(rng.lognormal(np.log(base_q), 0.5))))
        if o.cliente_id == S5_CLI:
            q = int(q * 2.5)
        lin.append((o.pedido_id, s, q))
det = pd.DataFrame(lin, columns=["pedido_id", "sku", "cantidad"])
det = det.merge(pedidos[["pedido_id", "fecha", "ciudad", "segmento", "vendedor_id"]], on="pedido_id")
if S3_SKU in set(det.sku):  # demanda de la bebida estrella sube en septiembre (temporada de calor)
    m3 = (det.sku == S3_SKU) & (det.fecha >= "2026-09-01")
    det.loc[m3, "cantidad"] = (det.loc[m3, "cantidad"] * 1.35).round().astype(int)
det["linea_n"] = det.groupby("pedido_id").cumcount() + 1
det["precio_lista"] = vigente(lista_precios, "precio_lista", det.sku.values, det.fecha.values)
det["costo_unitario"] = vigente(costos, "costo_unitario", det.sku.values, det.fecha.values)

# Descuentos según segmento (la mayoría bajo el tope de la política)
media = {"Grandes superficies": 11, "Mayoristas": 8, "Minoristas": 3, "Institucional": 5}
tope = {s: SEGMENTOS[s][4] for s in SEGMENTOS}
d = np.array([rng.normal(media[s], 2.2) for s in det.segmento])
d = np.clip(d, 0, [tope[s] for s in det.segmento])
especial = rng.random(len(det)) < 0.002
d = np.where(especial, [tope[s] + rng.integers(1, 4) for s in det.segmento], d)
det["descuento_pct"] = np.round(d, 1)
det["aprobacion_especial"] = np.where(especial, "S", "N")
# Escenario 4: vendedor que excede el tope
m4 = (det.vendedor_id == S4_VEND) & (det.fecha >= S4_DESDE) & det.segmento.isin(["Minoristas", "Mayoristas"]) & (rng.random(len(det)) < 0.7)
det.loc[m4, "descuento_pct"] = np.round(rng.uniform(18, 25, m4.sum()), 1)
det.loc[m4, "aprobacion_especial"] = "N"
det["precio_unitario"] = det.precio_lista
det["valor_neto"] = (det.cantidad * det.precio_unitario * (1 - det.descuento_pct / 100)).round(0)
pedidos_detalle = det[["pedido_id", "linea_n", "sku", "cantidad", "precio_lista", "precio_unitario", "descuento_pct",
                       "aprobacion_especial", "valor_neto", "costo_unitario"]].copy()

# ----------------------------------------------------------------------------------------
# Facturas y pagos
# ----------------------------------------------------------------------------------------
fac = pedidos[pedidos.estado == "Facturado"][["pedido_id", "cliente_id", "fecha"]].copy()
fac["fecha_factura"] = fac.fecha + pd.to_timedelta(rng.integers(0, 2, len(fac)), unit="D")
fac = fac[fac.fecha_factura <= FIN]
tot = pedidos_detalle.groupby("pedido_id").valor_neto.sum()
fac["valor_neto"] = fac.pedido_id.map(tot).values
fac["iva"] = (fac.valor_neto * 0.19).round(0)
fac["valor_total"] = fac.valor_neto + fac.iva
fac = fac.merge(clientes[["cliente_id", "plazo_dias"]], on="cliente_id")
fac["fecha_vencimiento"] = fac.fecha_factura + pd.to_timedelta(fac.plazo_dias, unit="D")
fac = fac.sort_values(["fecha_factura", "pedido_id"]).reset_index(drop=True)
fac["factura_id"] = [f"FE-{i+1:06d}" for i in range(len(fac))]

off = dict(zip(clientes.cliente_id, np.clip(rng.normal(2, 6, len(clientes)), -10, 20)))
dias_pago = fac.plazo_dias + fac.cliente_id.map(off) + rng.normal(0, 4, len(fac))
# Escenario 2: el cliente pasa de pagar a ~30 días a ~75 días
m2 = fac.cliente_id == S2_CLI
mes = fac.fecha_factura.dt.to_period("M").astype(str)
obj = {"2026-04": 38, "2026-05": 46, "2026-06": 56, "2026-07": 66, "2026-08": 75, "2026-09": 78}
dias_pago = np.where(m2, [obj.get(mm, 30) + rng.normal(0, 3) for mm in mes], dias_pago)
dias_pago = np.maximum(1, np.round(dias_pago)).astype(int)
fac["_fp"] = fac.fecha_factura + pd.to_timedelta(dias_pago, unit="D")
incobrable = (~m2) & (rng.random(len(fac)) < 0.005) & (fac.fecha_factura < "2026-06-01")
fac.loc[incobrable, "_fp"] = pd.NaT
pag = fac[fac._fp.notna() & (fac._fp <= FIN)][["factura_id", "_fp", "valor_total"]].copy()
pag.columns = ["factura_id", "fecha_pago", "valor"]
pag["medio_pago"] = rng.choice(["Transferencia", "PSE", "Cheque", "Consignación"], size=len(pag), p=[0.6, 0.2, 0.08, 0.12])
pag = pag.sort_values(["fecha_pago", "factura_id"]).reset_index(drop=True)
pag["pago_id"] = [f"PG-{i+1:06d}" for i in range(len(pag))]
facturas = fac[["factura_id", "pedido_id", "cliente_id", "fecha_factura", "fecha_vencimiento", "valor_neto", "iva", "valor_total"]]
pagos = pag[["pago_id", "factura_id", "fecha_pago", "valor", "medio_pago"]]

# ----------------------------------------------------------------------------------------
# Inventario diario y órdenes de compra (simulación por SKU y bodega)
# ----------------------------------------------------------------------------------------
desp = det.merge(pedidos[["pedido_id", "estado"]], on="pedido_id")
desp = desp[desp.estado == "Facturado"].merge(fac[["pedido_id", "fecha_factura"]], on="pedido_id")
desp["bodega_id"] = desp.ciudad.map({c: v[1] for c, v in CIUDADES.items()})
dem = desp.groupby(["sku", "bodega_id", "fecha_factura"]).cantidad.sum()
lead = dict(zip(proveedores.proveedor_id, proveedores.lead_time_dias))
prov_sku = dict(zip(productos.sku, productos.proveedor_id))
inv_rows, oc_rows = [], []
oc_n = 0

def simular(sku, bod, bloqueo=None, parcial=None, sin_tope=False):
    """Simula existencias. `bloqueo`: desde esa fecha el proveedor no entrega (retraso).
    `parcial`: (fecha, cantidad) entrega urgente parcial. `sin_tope`: permite existencia negativa (cálculo)."""
    serie = dem.loc[(sku, bod)] if (sku, bod) in dem.index else pd.Series(dtype=float)
    d = serie.reindex(DIAS, fill_value=0).values.astype(float)
    lt = int(lead[prov_sku[sku]])
    hist = list(d[:30]) if d[:30].sum() > 0 else [0.5]
    stock = round(max(np.mean(d[:60]) * 40, d[:60].max() * 2, 20)); filas = []; ocs = []
    for t, dia in enumerate(DIAS):
        ini = stock; ent = 0
        for oc in [o for o in ocs if o["estado"] == "En tránsito" and o["fecha_esperada"] == dia]:
            if bloqueo is not None and dia >= bloqueo:
                oc["estado"] = "Retrasada"; continue
            ent += oc["cantidad"]; oc["estado"] = "Recibida"; oc["fecha_recibida"] = dia
        if parcial is not None and dia == parcial[0]:
            ocs.append({"sku": sku, "bodega_id": bod, "proveedor_id": prov_sku[sku], "fecha_oc": dia - pd.Timedelta(days=2),
                        "fecha_esperada": dia, "fecha_recibida": dia, "cantidad": int(parcial[1]), "estado": "Recibida"})
            ent += int(parcial[1])
        sal = d[t] if sin_tope else min(d[t], ini + ent)
        stock = ini + ent - sal
        hist = (hist + [d[t]])[-30:]
        mu, sd = float(np.mean(hist)), float(np.std(hist))
        rop = mu * (lt + 10) + 2.5 * sd * np.sqrt(lt) + max(hist)
        transito = sum(o["cantidad"] for o in ocs if o["estado"] in ("En tránsito", "Retrasada"))
        if stock + transito < rop:
            ocs.append({"sku": sku, "bodega_id": bod, "proveedor_id": prov_sku[sku], "fecha_oc": dia,
                        "fecha_esperada": dia + pd.Timedelta(days=lt), "fecha_recibida": pd.NaT,
                        "cantidad": int(round(max(mu * 30, 2 * max(hist), 10))), "estado": "En tránsito"})
        filas.append((dia, bod, sku, int(ini), int(ent), int(sal), int(stock)))
    return filas, ocs

for sku in productos.sku:
    for bod in BODEGAS.bodega_id:
        if sku == S3_SKU and bod == S3_BOD:
            continue
        f, o = simular(sku, bod)
        inv_rows += f; oc_rows += o
# Escenario 3: el proveedor de la bebida estrella se retrasa; una entrega urgente parcial
# no alcanza y al cierre quedan menos de 5 días de cobertura con pedidos pendientes.
S3_CORTE = None
for corte in pd.date_range("2026-09-10", "2026-08-01", freq="-1D"):
    f, o = simular(S3_SKU, S3_BOD, bloqueo=corte, sin_tope=True)
    st = np.array([r[6] for r in f])
    if st[-1] < 0:
        S3_CORTE = corte; break
dprom = np.array([r[5] for r in f])[-30:].mean()
cero = int(np.argmax(st < dprom * 2))
fecha_p = DIAS[max(cero - 1, 0)]
cant_p = int(round(dprom * 3.5 - st[-1]))
f, o = simular(S3_SKU, S3_BOD, bloqueo=S3_CORTE, parcial=(fecha_p, cant_p))
inv_rows += f; oc_rows += o
inventario = pd.DataFrame(inv_rows, columns=["fecha", "bodega_id", "sku", "existencia_inicial", "entradas", "salidas", "existencia_final"])
inventario = inventario.sort_values(["fecha", "bodega_id", "sku"]).reset_index(drop=True)
ordenes_compra = pd.DataFrame(oc_rows).sort_values(["fecha_oc", "sku", "bodega_id"]).reset_index(drop=True)
ordenes_compra["oc_id"] = [f"OC-{i+1:06d}" for i in range(len(ordenes_compra))]
precio_oc = vigente(costos, "costo_unitario", ordenes_compra.sku.values, ordenes_compra.fecha_oc.values)
ordenes_compra["costo_unitario"] = precio_oc
ordenes_compra = ordenes_compra[["oc_id", "proveedor_id", "sku", "bodega_id", "fecha_oc", "fecha_esperada",
                                 "fecha_recibida", "cantidad", "costo_unitario", "estado"]]

# ----------------------------------------------------------------------------------------
# Atributos derivados y exportación
# ----------------------------------------------------------------------------------------
ventas_sku = pedidos_detalle.merge(pedidos[["pedido_id", "estado"]], on="pedido_id").query("estado != 'Cancelado'").groupby("sku").valor_neto.sum()
orden = ventas_sku.sort_values(ascending=False); acum = orden.cumsum() / orden.sum()
abc = {s: ("A" if a <= 0.8 else "B" if a <= 0.95 else "C") for s, a in acum.items()}
productos["clase_abc"] = productos.sku.map(abc).fillna("C")
productos["unidad"] = "UND"
productos_out = productos[["sku", "nombre", "linea", "proveedor_id", "clase_abc", "unidad"]]
cupo = (pedidos_detalle.merge(pedidos[["pedido_id", "cliente_id"]], on="pedido_id").groupby("cliente_id").valor_neto.sum() / 12 * 2).round(-6)
clientes["cupo_credito"] = clientes.cliente_id.map(cupo).fillna(5_000_000).clip(lower=5_000_000).astype(int)
clientes_out = clientes[["cliente_id", "nombre", "segmento", "ciudad", "region", "vendedor_id", "plazo_dias", "cupo_credito", "fecha_alta"]]
pedidos_out = pedidos[["pedido_id", "fecha", "cliente_id", "vendedor_id", "ciudad", "canal", "estado"]]

os.makedirs(SALIDA, exist_ok=True)
tablas = {"clientes": clientes_out, "vendedores": vendedores, "productos": productos_out, "proveedores": proveedores,
          "bodegas": BODEGAS, "lista_precios": lista_precios, "costos_proveedor": costos, "ordenes_compra": ordenes_compra,
          "pedidos": pedidos_out, "pedidos_detalle": pedidos_detalle, "facturas": facturas, "pagos": pagos,
          "inventario_diario": inventario}
for nombre, df in tablas.items():
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    df.to_csv(os.path.join(SALIDA, f"{nombre}.csv"), index=False, encoding="utf-8")
    print(f"{nombre:20s} {len(df):>8,d} filas")

ESCENARIOS = {"semilla": SEMILLA, "s1_proveedor": S1_PROV, "s1_skus": S1_SKUS, "s1_fecha": str(S1_FECHA.date()),
              "s2_cliente": S2_CLI, "s3_sku": S3_SKU, "s3_bodega": S3_BOD, "s3_corte_proveedor": str(S3_CORTE.date()),
              "s3_entrega_parcial": [str(fecha_p.date()), cant_p], "s4_vendedor": S4_VEND, "s4_desde": str(S4_DESDE.date()), "s5_cliente": S5_CLI, "s5_ultima_compra_aprox": str(S5_FIN.date())}
if os.environ.get("GUARDAR_ESCENARIOS"):
    import json
    with open(os.environ["GUARDAR_ESCENARIOS"], "w", encoding="utf-8") as fh:
        json.dump(ESCENARIOS, fh, ensure_ascii=False, indent=2)
