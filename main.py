import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from groq import Groq

import db
import schemas

CATEGORIAS = [
    "Supermercado", "Transporte", "Ocio", "Salud",
    "Gastos Fijos", "Ropa", "Suministros", "Otros"
]

# Se crea el cliente de Groq
groq_client = None

# Se define que debe hacer el servidor cuando se inicia y se detiene
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.crear_tablas()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Ruta raíz ──────────────────────────────────────────────────────────────────

@app.get("/")
def raiz():
    return FileResponse(
        "static/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# ── Gastos ─────────────────────────────────────────────────────────────────────

# Se obtiene la lista de gastos
@app.get("/gastos", response_model=list[schemas.GastoOut])
def obtener_gastos(categoria: str | None = None, mes: str | None = None):
    filas = db.obtener_gastos(categoria=categoria, mes=mes)
    return [schemas.GastoOut.model_validate(dict(f)) for f in filas]


# Se crea un gasto
@app.post("/gastos", response_model=schemas.GastoOut, status_code=201)
def crear_gasto(gasto: schemas.GastoCreate):
    id = db.añadir_gasto(
        gasto.descripcion,
        gasto.importe,
        gasto.categoria,
        gasto.fecha,
    )
    return schemas.GastoOut.model_validate(dict(db.obtener_gasto(id)))


# Se edita un gasto
@app.put("/gastos/{id}", response_model=schemas.GastoOut)
def editar_gasto(id: int, gasto: schemas.GastoUpdate):
    existe = db.obtener_gasto(id)
    if not existe:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db.editar_gasto(
        id,
        gasto.descripcion,
        gasto.importe,
        gasto.categoria,
        gasto.fecha,
    )
    return schemas.GastoOut.model_validate(dict(db.obtener_gasto(id)))


# Se elimina un gasto
@app.delete("/gastos/{id}", status_code=204)
def eliminar_gasto(id: int):
    eliminado = db.eliminar_gasto(id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")


# ── Presupuestos ───────────────────────────────────────────────────────────────

@app.get("/presupuestos/{mes}", response_model=schemas.PresupuestoOut)
def obtener_presupuesto(mes: str):
    """
    Devuelve el presupuesto de un mes junto con lo gastado y lo restante.
    mes tiene el formato "2026-03".
    """
    importe = db.obtener_presupuesto(mes)
    if importe is None:
        raise HTTPException(status_code=404, detail="Presupuesto no definido")

    # Calculamos lo gastado sumando todos los gastos del mes
    gastos_mes = db.obtener_gastos(mes=mes)
    gastado = sum(g["importe"] for g in gastos_mes)

    return schemas.PresupuestoOut(
        mes=mes,
        importe=importe,
        gastado=round(gastado, 2),
        restante=round(importe - gastado, 2)
    )


@app.put("/presupuestos/{mes}", response_model=schemas.PresupuestoOut)
def guardar_presupuesto(mes: str, datos: schemas.PresupuestoIn):
    """
    Crea o actualiza el presupuesto de un mes.
    Usamos PUT porque es una operación idempotente:
    llamarla varias veces con el mismo valor produce el mismo resultado.
    """
    db.guardar_presupuesto(mes, datos.importe)

    gastos_mes = db.obtener_gastos(mes=mes)
    gastado = sum(g["importe"] for g in gastos_mes)

    return schemas.PresupuestoOut(
        mes=mes,
        importe=datos.importe,
        gastado=round(gastado, 2),
        restante=round(importe - gastado, 2)
    )

@app.get("/static/manifest.json")
def manifest():
    return FileResponse("static/manifest.json")

@app.get("/static/sw.js")
def service_worker():
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/"
        }
    )
# ── IA ─────────────────────────────────────────────────────────────────────────

@app.post("/ia/categorizar", response_model=schemas.CategorizarResponse)
def categorizar(request: schemas.CategorizarRequest):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    mensaje = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": (
                f'Gasto: "{request.descripcion}". '
                f'Categorías posibles: {", ".join(CATEGORIAS)}. '
                f'Responde SOLO con el nombre exacto de una categoría.'
            )
        }]
    )
    categoria = mensaje.choices[0].message.content.strip()
    if categoria not in CATEGORIAS:
        categoria = "Otros"
    return schemas.CategorizarResponse(categoria=categoria)