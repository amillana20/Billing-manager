import sqlite3
import pathlib
from datetime import date

# Ruta de la base de datos
DB_PATH = pathlib.Path.home() / ".gastos_ia.db"

def _get_conn() -> sqlite3.Connection:
    # Conectar a la base de datos
    conn = sqlite3.connect(DB_PATH)
    # Devolver los resultados como diccionarios en vez de tuplas
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas() -> None:
    # Crear las tablas si no existen
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT    NOT NULL,
                importe     REAL    NOT NULL CHECK(importe > 0),
                categoria   TEXT    NOT NULL,
                fecha       TEXT    NOT NULL
            )
        """)


def añadir_gasto(descripcion: str, importe: float, categoria: str, fecha: date | None = None) -> int:
    # Añadir un gasto a la base de datos

    # Convertir la fecha a string en formato ISO 8601. Si no hay datos, es el día actual.
    fecha_str = (fecha or date.today()).isoformat()

    # Conectar a la base de datos
    with _get_conn() as conn:
        # Ejecutar la consulta para añadir el gasto
        cursor = conn.execute(
            """
            INSERT INTO gastos (descripcion, importe, categoria, fecha)
            VALUES (?, ?, ?, ?)
            """,
            (descripcion, importe, categoria, fecha_str),
        )
        # Devolver el id del gasto añadido
        return cursor.lastrowid

def obtener_gastos(
    categoria: str | None = None,
    mes: str | None = None,
) -> list[sqlite3.Row]:
    # Obtener los gastos de la base de datos
    # Se puede filtrar por categoría y mes
    # Se ordenan por fecha y id

    query = "SELECT * FROM gastos WHERE 1=1"
    params: list = []

    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)

    if mes:
        query += " AND strftime('%Y-%m', fecha) = ?"
        params.append(mes)

    query += " ORDER BY fecha DESC, id DESC"

    with _get_conn() as conn:
        return conn.execute(query, params).fetchall()

def obtener_gasto(id: int) -> sqlite3.Row | None:
    # Obtener un gasto por su id
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM gastos WHERE id = ?", [id]
        ).fetchone()

def editar_gasto(
    id: int,
    descripcion: str,
    importe: float,
    categoria: str,
    fecha: date,
) -> bool:
    # Editar un gasto por su id
    with _get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE gastos
            SET descripcion = ?,
                importe     = ?,
                categoria   = ?,
                fecha       = ?
            WHERE id = ?
            """,
            (descripcion, importe, categoria, fecha.isoformat(), id),
        )
        return cursor.rowcount > 0

def eliminar_gasto(id: int) -> bool:
    # Eliminar un gasto por su id
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM gastos WHERE id = ?", [id]
        )
        return cursor.rowcount > 0

def totales_por_categoria(mes: str | None = None) -> list[dict]:
    # Obtener los totales de los gastos por categoría
    # Se puede filtrar por mes
    # Se ordenan por total de mayor a menor

    query = "SELECT categoria, SUM(importe) as total FROM gastos"
    params: list = []

    if mes:
        query += " WHERE strftime('%Y-%m', fecha) = ?"
        params.append(mes)

    query += " GROUP BY categoria ORDER BY total DESC"

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [{"categoria": r["categoria"], "total": r["total"]} for r in rows]



if __name__ == "__main__":
    crear_tablas()

    id1 = añadir_gasto("Mercadona", 67.50, "Alimentación")
    id2 = añadir_gasto("Netflix", 17.99, "Ocio")
    id3 = añadir_gasto("Renfe Madrid-Valencia", 42.00, "Transporte")

    print("Todos los gastos:")
    for g in obtener_gastos():
        print(f"  {g['id']} | {g['descripcion']} | {g['importe']}€ | {g['categoria']}")

    print("\nSolo Ocio:")
    for g in obtener_gastos(categoria="Ocio"):
        print(f"  {g['descripcion']} | {g['importe']}€")

    from datetime import date
    editar_gasto(id1, "Mercadona (editado)", 70.00, "Alimentación", date.today())
    print(f"\nGasto editado: {dict(obtener_gasto(id1))}")

    print("\nTotales por categoría:", totales_por_categoria())

    eliminar_gasto(id3)
    print(f"\nGastos tras eliminar: {len(obtener_gastos())}")
