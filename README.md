# Gestión de gastos

App personal para gestionar gastos compartidos.

## Tecnologías

- **Backend**: Python + FastAPI
- **Base de datos**: PostgreSQL (Supabase)
- **Frontend**: HTML + CSS + JavaScript

## Funcionalidades

- Añadir, editar y eliminar gastos
- Gastos fijos y presupuesto mensual
- Gráfico de gastos por categoría
- Accesible desde móvil y escritorio

## Categorías

Supermercado, Transporte, Ocio, Salud, Gastos Fijos, Ropa, Suministros, Otros

## Instalación local

1. Clona el repositorio
2. Instala las dependencias
```bash
    pip install -r requirements.txt
```
3. Define las variables de entorno `DATABASE_URL`, `SECRET_KEY` y `USUARIOS` (ver «Acceso» más abajo)
4. Arranca el servidor
```bash
    uvicorn main:app --reload
```
5. Abre el navegador en `http://localhost:8000`

## Acceso (login)

La app pide usuario y contraseña. Hay dos usuarios que comparten los mismos gastos.
Se configuran con dos variables de entorno (en Render: *Environment*):

| Variable     | Valor |
|--------------|-------|
| `SECRET_KEY` | Clave aleatoria larga (mínimo 32 caracteres) para firmar la sesión |
| `USUARIOS`   | `nombre1:hash1,nombre2:hash2` |

Para generar el hash de cada contraseña (y una `SECRET_KEY`):

```bash
python auth.py
```

- Cambiar la contraseña de un usuario cierra sus sesiones abiertas.
- Cambiar `SECRET_KEY` cierra las sesiones de los dos.
- `/health` sigue siendo público para el keep-alive.
