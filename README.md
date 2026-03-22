# Gastos IA

App personal para gestionar gastos con categorización automática mediante IA.

## Tecnologías

- **Backend**: Python + FastAPI
- **Base de datos**: SQLite
- **IA**: Claude (Anthropic)
- **Frontend**: HTML + CSS + JavaScript

## Funcionalidades

- Añadir, editar y eliminar gastos
- Categorización automática con IA
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
3. Arranca el servidor
```bash
    set ANTHROPIC_API_KEY=sk-ant-...
    uvicorn main:app --reload
```
4. Abre el navegador en `http://localhost:8000`