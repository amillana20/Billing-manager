import os
from contextlib import asynccontextmanager
from datetime import date

import asyncio
import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from groq import Groq

import auth
import db
import schemas

logger = logging.getLogger("uvicorn.error")

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
    if not auth.configurado():
        logger.error(
            "Faltan SECRET_KEY (mín. 32 caracteres) o USUARIOS: "
            "nadie podrá iniciar sesión. Ejecuta 'python auth.py'."
        )
    yield


app = FastAPI(lifespan=lifespan)


# ── Autenticación ──────────────────────────────────────────────────────────────

# Rutas que se pueden visitar sin haber iniciado sesión.
RUTAS_PUBLICAS = {"/login", "/health"}


@app.middleware("http")
async def exigir_login(request: Request, call_next):
    ruta = request.url.path

    # Protección CSRF: una petición que modifica datos tiene que venir de
    # nuestra propia web. (La cookie SameSite=Lax ya lo cubre en navegadores
    # modernos; esto es una segunda barrera.)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origen = request.headers.get("origin")
        if origen and urlsplit(origen).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)

    if ruta in RUTAS_PUBLICAS or ruta.startswith("/static/"):
        return await call_next(request)

    usuario = auth.usuario_de_token(request.cookies.get(auth.COOKIE_NOMBRE))
    if usuario is None:
        # La página principal redirige al login; la API responde 401.
        if ruta == "/":
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "No autenticado"}, status_code=401)

    request.state.usuario = usuario
    return await call_next(request)


def _ip(request: Request) -> str:
    # Render pone la IP real del cliente en X-Forwarded-For.
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


@app.get("/login")
def pagina_login(request: Request):
    if auth.usuario_de_token(request.cookies.get(auth.COOKIE_NOMBRE)):
        return RedirectResponse("/", status_code=303)
    return FileResponse("static/login.html", headers={"Cache-Control": "no-store"})


@app.post("/login")
async def login(datos: schemas.LoginRequest, request: Request):
    ip = _ip(request)
    if auth.bloqueado(ip):
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera unos minutos.",
        )
    if not auth.configurado():
        raise HTTPException(status_code=503, detail="Login no configurado en el servidor")

    # PBKDF2 tarda un poco a propósito: lo sacamos del bucle de eventos.
    ok = await asyncio.to_thread(auth.autenticar, datos.usuario, datos.password)
    if not ok:
        auth.registrar_fallo(ip)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    auth.limpiar_fallos(ip)
    respuesta = JSONResponse({"usuario": datos.usuario})
    respuesta.set_cookie(
        auth.COOKIE_NOMBRE,
        auth.crear_token(datos.usuario),
        max_age=auth.DURACION_SESION,
        httponly=True,   # JavaScript no puede leerla
        secure=request.url.hostname not in ("localhost", "127.0.0.1"),
        samesite="lax",
    )
    return respuesta


@app.post("/logout")
def logout():
    respuesta = JSONResponse({"ok": True})
    respuesta.delete_cookie(auth.COOKIE_NOMBRE, httponly=True, samesite="lax")
    return respuesta


@app.get("/yo")
def yo(request: Request):
    return {"usuario": request.state.usuario}

# Primero las rutas específicas
@app.get("/static/sw.js")
def service_worker():
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )

@app.get("/static/manifest.json")
def manifest():
    return FileResponse(
        "static/manifest.json",
        media_type="application/manifest+json"
    )

# Después el mount general
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


# ── Health check ───────────────────────────────────────────────────────────────

# Endpoint ligero que visita GitHub Actions cada 10 minutos para que Render
# no duerma la app. También hace una consulta mínima a la base de datos para
# que Supabase no la pause por inactividad.
@app.get("/health")
def health():
    try:
        db.comprobar_conexion()
    except Exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    return {"status": "ok"}


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
        restante=round(datos.importe - gastado, 2)
    )


# ── Gastos fijos ───────────────────────────────────────────────────────────────

@app.get("/gastos-fijos", response_model=list[schemas.GastoFijoOut])
def obtener_gastos_fijos():
    return [schemas.GastoFijoOut.model_validate(f) for f in db.obtener_gastos_fijos()]


@app.post("/gastos-fijos", response_model=schemas.GastoFijoOut, status_code=201)
def crear_gasto_fijo(gasto: schemas.GastoFijoCreate):
    id = db.añadir_gasto_fijo(gasto.descripcion, gasto.importe, gasto.categoria)
    return schemas.GastoFijoOut.model_validate(db.obtener_gasto_fijo(id))


@app.put("/gastos-fijos/{id}", response_model=schemas.GastoFijoOut)
def editar_gasto_fijo(id: int, gasto: schemas.GastoFijoUpdate):
    existe = db.obtener_gasto_fijo(id)
    if not existe:
        raise HTTPException(status_code=404, detail="Gasto fijo no encontrado")
    db.editar_gasto_fijo(id, gasto.descripcion, gasto.importe, gasto.categoria)
    return schemas.GastoFijoOut.model_validate(db.obtener_gasto_fijo(id))


@app.delete("/gastos-fijos/{id}", status_code=204)
def eliminar_gasto_fijo(id: int):
    eliminado = db.eliminar_gasto_fijo(id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Gasto fijo no encontrado")


@app.post("/empezar-mes", response_model=schemas.EmpezarMesResponse)
def empezar_mes(datos: schemas.EmpezarMesRequest):
    insertados, omitidos = db.empezar_mes(datos.mes)
    return schemas.EmpezarMesResponse(mes=datos.mes, insertados=insertados, omitidos=omitidos)


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