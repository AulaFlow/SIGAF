"""Quién hace la petición: usuario_actual() y requiere_rol() (issue #11, Salva).

ARCHIVO PROVISIONAL (issue #23, alex). Las rutas ya dependen de estas firmas, pero
el login con JWT lo hace Salva en el #11 y reemplazará el contenido de usuario_actual().
Mientras tanto toda ruta protegida responde 401: en el código de la app no hay ningún
usuario falso (los de prueba viven solo en tests/, con dependency_overrides).

Acuerdo con el #11:
- usuario_actual() regresa Alumno, Profesor o Administrador armado con los datos del
  token (nunca del body ni de la URL). Sin token válido: 401.
- requiere_rol(*roles) deja pasar solo esos roles. Rol equivocado: 403.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .dominio.personas import Persona, Rol

esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT de POST /auth/login (#11)")

NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Inicia sesión para continuar",
    headers={"WWW-Authenticate": "Bearer"},
)


def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
) -> Persona:
    """Lee el token y regresa la persona. Provisional: siempre 401 hasta el #11."""
    raise NO_AUTENTICADO


UsuarioActual = Annotated[Persona, Depends(usuario_actual)]


def requiere_rol(*roles: Rol) -> Callable[..., Persona]:
    """Dependencia que solo deja pasar a esos roles (403 a los demás)."""
    if not roles:
        raise ValueError("requiere_rol necesita al menos un rol")

    def verificar(persona: UsuarioActual) -> Persona:
        if not persona.es(*roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Tu rol no tiene permiso para esta operación")
        return persona

    return verificar
