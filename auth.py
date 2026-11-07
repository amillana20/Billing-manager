"""
Autenticación sencilla para dos usuarios que comparten los mismos gastos.

Configuración (variables de entorno en Render):

    SECRET_KEY  Clave aleatoria larga para firmar la cookie de sesión.
    USUARIOS    Lista "nombre:hash" separada por comas, por ejemplo:
                alex:pbkdf2_sha256$600000$...,marta:pbkdf2_sha256$600000$...

Para generar el hash de una contraseña (y una SECRET_KEY nueva):

    python auth.py

Solo usa la librería estándar de Python: no hace falta instalar nada.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import time

COOKIE_NOMBRE = "sesion"
DURACION_SESION = 30 * 24 * 3600  # 30 días
ITERACIONES = 600_000
_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


# ── Contraseñas ────────────────────────────────────────────────────────────────

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${_b64(salt)}${_b64(dk)}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, salt, esperado = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _unb64(salt), int(iteraciones)
        )
        return hmac.compare_digest(dk, _unb64(esperado))
    except (ValueError, TypeError):
        return False


# ── Configuración ──────────────────────────────────────────────────────────────

def _usuarios() -> dict[str, str]:
    """Lee USUARIOS del entorno: {"nombre": "hash"}."""
    resultado = {}
    for entrada in os.environ.get("USUARIOS", "").split(","):
        entrada = entrada.strip()
        if not entrada or ":" not in entrada:
            continue
        nombre, hash_ = entrada.split(":", 1)
        nombre = nombre.strip()
        if _NOMBRE_VALIDO.match(nombre):
            resultado[nombre] = hash_.strip()
    return resultado


def _secret() -> bytes | None:
    s = os.environ.get("SECRET_KEY", "")
    return s.encode() if len(s) >= 32 else None


def configurado() -> bool:
    return _secret() is not None and bool(_usuarios())


# Hash ficticio para que comprobar un usuario inexistente tarde lo mismo
# que uno existente (así no se puede adivinar qué usuarios existen).
_HASH_FALSO = hash_password(secrets.token_hex(16))


def autenticar(nombre: str, password: str) -> bool:
    if not configurado():
        return False
    guardado = _usuarios().get(nombre)
    if guardado is None:
        verificar_password(password, _HASH_FALSO)
        return False
    return verificar_password(password, guardado)


# ── Sesión (cookie firmada) ────────────────────────────────────────────────────
# Formato: nombre.caducidad.firma
# La firma incluye el hash de la contraseña del usuario: si cambias su
# contraseña en Render, sus sesiones abiertas dejan de valer. Si quitas al
# usuario de USUARIOS, también.

def _firma(nombre: str, caducidad: int, hash_: str, secret: bytes) -> str:
    msg = f"{nombre}.{caducidad}.{hash_}".encode()
    return _b64(hmac.new(secret, msg, hashlib.sha256).digest())


def crear_token(nombre: str) -> str:
    secret = _secret()
    hash_ = _usuarios()[nombre]
    caducidad = int(time.time()) + DURACION_SESION
    return f"{nombre}.{caducidad}.{_firma(nombre, caducidad, hash_, secret)}"


def usuario_de_token(token: str | None) -> str | None:
    """Devuelve el nombre de usuario si el token es válido, si no None."""
    if not token:
        return None
    secret = _secret()
    if secret is None:
        return None
    try:
        nombre, caducidad_str, firma = token.split(".")
        caducidad = int(caducidad_str)
    except ValueError:
        return None
    if caducidad < time.time():
        return None
    hash_ = _usuarios().get(nombre)
    if hash_ is None:
        return None
    if not hmac.compare_digest(firma, _firma(nombre, caducidad, hash_, secret)):
        return None
    return nombre


# ── Límite de intentos de login ────────────────────────────────────────────────
# En memoria: se reinicia si se reinicia el servidor, suficiente para frenar
# a alguien que pruebe contraseñas a lo bruto.

MAX_FALLOS = 10
VENTANA = 15 * 60  # 15 minutos
_fallos: dict[str, list[float]] = {}


def bloqueado(ip: str) -> bool:
    ahora = time.time()
    recientes = [t for t in _fallos.get(ip, []) if ahora - t < VENTANA]
    _fallos[ip] = recientes
    return len(recientes) >= MAX_FALLOS


def registrar_fallo(ip: str) -> None:
    _fallos.setdefault(ip, []).append(time.time())


def limpiar_fallos(ip: str) -> None:
    _fallos.pop(ip, None)


# ── Utilidad de línea de comandos ──────────────────────────────────────────────

if __name__ == "__main__":
    import getpass

    nombre = input("Nombre de usuario (letras, números, - o _): ").strip()
    if not _NOMBRE_VALIDO.match(nombre):
        raise SystemExit("Nombre no válido.")
    p1 = getpass.getpass("Contraseña: ")
    p2 = getpass.getpass("Repite la contraseña: ")
    if p1 != p2:
        raise SystemExit("Las contraseñas no coinciden.")
    if len(p1) < 10:
        raise SystemExit("Usa al menos 10 caracteres.")
    print("\nAñade esto a USUARIOS en Render (separa los dos usuarios con una coma):\n")
    print(f"{nombre}:{hash_password(p1)}")
    print("\nSi aún no tienes SECRET_KEY, puedes usar esta:\n")
    print(secrets.token_urlsafe(48))
