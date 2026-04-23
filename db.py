import os
import psycopg2
import psycopg2.extras
from datetime import date

# En local usa SQLite, en producción usa PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL")


def _get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def crear_tablas() -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gastos (
                    id          SERIAL PRIMARY KEY,
                    descripcion TEXT   NOT NULL,
                    importe     REAL   NOT NULL CHECK(importe > 0),
                    categoria   TEXT   NOT NULL,
                    fecha       TEXT   NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS presupuestos (
                    mes     TEXT PRIMARY KEY,
                    importe REAL NOT NULL CHECK(importe > 0)
                )
            """)
        conn.commit()


def añadir_gasto(
    descripcion: str,
    importe: float,
    categoria: str,
    fecha: date | None = None,
) -> int:
    fecha_str = (fecha or date.today()).isoformat()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gastos (descripcion, importe, categoria, fecha)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (descripcion, importe, categoria, fecha_str),
            )
            id = cur.fetchone()[0]
        conn.commit()
        return id


def obtener_gastos(
    categoria: str | None = None,
    mes: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM gastos WHERE 1=1"
    params = []

    if categoria:
        query += " AND categoria = %s"
        params.append(categoria)

    if mes:
        query += " AND SUBSTRING(fecha, 1, 7) = %s"
        params.append(mes)

    query += " ORDER BY fecha DESC, id DESC"

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def obtener_gasto(id: int) -> dict | None:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM gastos WHERE id = %s", (id,))
            fila = cur.fetchone()
            return dict(fila) if fila else None


def editar_gasto(
    id: int,
    descripcion: str,
    importe: float,
    categoria: str,
    fecha: date,
) -> bool:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE gastos
                SET descripcion = %s,
                    importe     = %s,
                    categoria   = %s,
                    fecha       = %s
                WHERE id = %s
                """,
                (descripcion, importe, categoria, fecha.isoformat(), id),
            )
            affected = cur.rowcount
        conn.commit()
        return affected > 0


def eliminar_gasto(id: int) -> bool:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gastos WHERE id = %s", (id,))
            affected = cur.rowcount
        conn.commit()
        return affected > 0


def totales_por_categoria(mes: str | None = None) -> list[dict]:
    query = "SELECT categoria, SUM(importe) as total FROM gastos"
    params = []

    if mes:
        query += " WHERE SUBSTRING(fecha, 1, 7) = %s"
        params.append(mes)

    query += " GROUP BY categoria ORDER BY total DESC"

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def obtener_presupuesto(mes: str) -> float | None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT importe FROM presupuestos WHERE mes = %s", (mes,)
            )
            fila = cur.fetchone()
            return fila[0] if fila else None


def guardar_presupuesto(mes: str, importe: float) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO presupuestos (mes, importe)
                VALUES (%s, %s)
                ON CONFLICT (mes) DO UPDATE SET importe = EXCLUDED.importe
                """,
                (mes, importe)
            )
        conn.commit()