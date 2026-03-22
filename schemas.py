from pydantic import BaseModel, Field, field_validator
from datetime import date


class GastoBase(BaseModel):
    """Campos comunes a crear y editar."""
    descripcion: str  = Field(min_length=1, max_length=200)
    importe:     float = Field(gt=0, description="Debe ser mayor que 0")
    categoria:   str  = Field(min_length=1, max_length=50)
    etiquetas:   list[str] = Field(default_factory=list)
    fecha:       date = Field(default_factory=date.today)

    @field_validator("descripcion", "categoria")
    @classmethod
    def no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("No puede estar vacío o contener solo espacios")
        return v.strip()

    @field_validator("etiquetas")
    @classmethod
    def limpiar_etiquetas(cls, v: list[str]) -> list[str]:
        return [tag.strip() for tag in v if tag.strip()]


class GastoCreate(GastoBase):
    """Lo que recibe la API al crear un gasto (POST)."""
    pass


class GastoUpdate(GastoBase):
    """Lo que recibe la API al editar un gasto (PUT)."""
    pass


class GastoOut(GastoBase):
    """Lo que devuelve la API. Incluye id."""
    id: int

    model_config = {"from_attributes": True}


class CategorizarRequest(BaseModel):
    """Petición al endpoint de IA."""
    descripcion: str = Field(min_length=1, max_length=200)


class CategorizarResponse(BaseModel):
    """Respuesta del endpoint de IA."""
    categoria: str