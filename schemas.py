from pydantic import BaseModel, Field, field_validator
from datetime import date


class GastoBase(BaseModel):
    # Se definen las condiciones de los campos
    descripcion: str   = Field(min_length=1, max_length=200)
    importe:     float = Field(gt=0)
    categoria:   str   = Field(min_length=1, max_length=50)
    fecha:       date  = Field(default_factory=date.today)

    # Se definen las validaciones de los campos descripcion y categoria
    # No puede estar vacío o contener solo espacios
    @field_validator("descripcion", "categoria")
    @classmethod
    def no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("No puede estar vacío o contener solo espacios")
        return v.strip()

class GastoCreate(GastoBase):
    pass


class GastoUpdate(GastoBase):
    pass


class GastoOut(GastoBase):
    id: int

    model_config = {"from_attributes": True}


class CategorizarRequest(BaseModel):
    descripcion: str = Field(min_length=1, max_length=200)


class CategorizarResponse(BaseModel):
    categoria: str

class PresupuestoIn(BaseModel):
    """Lo que recibe la API al guardar un presupuesto."""
    importe: float = Field(gt=0)


class PresupuestoOut(BaseModel):
    """Lo que devuelve la API con el presupuesto y el saldo restante."""
    mes:       str
    importe:   float  # presupuesto total del mes
    gastado:   float  # suma de todos los gastos del mes
    restante:  float  # importe - gastado