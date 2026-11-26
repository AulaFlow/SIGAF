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
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .dominio.personas import Administrador, Alumno, Persona, Profesor, Rol

esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT de POST /auth/login (#11)")

NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Inicia sesión para continuar",
    headers={"WWW-Authenticate": "Bearer"},
)

# ---------------------------------------------------------------------------
# Token de sesión (JWT firmado con HS256)
#
# El token NO está cifrado: cualquiera puede leer su contenido (es base64).
# Lo que impide falsificarlo es la FIRMA: sin SIGAF_JWT_LLAVE no se puede
# cambiar ni un claim sin que jwt.decode lo note. Por eso solo lleva lo que la
# API necesita para armar la Persona, y nunca la contraseña.
# ---------------------------------------------------------------------------
ALGORITMO = "HS256"
# Sin estos claims el token no sirve. "exp" hace que PyJWT rechace los vencidos.
CLAIMS_OBLIGATORIOS = ("sub", "rol", "correo", "iat", "exp")


def crear_token(persona: Persona, llave: str, minutos: int,
                ahora: datetime | None = None) -> str:
    """Firma un token con los datos de la persona. Dura `minutos` desde `ahora`."""
    ahora = ahora or datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(persona.usuario_id),          # PyJWT exige que "sub" sea texto
        "rol": persona.rol.value,
        "correo": persona.correo,
        "centro": persona.centro_academico_id,   # shard key; None para el administrador
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    if isinstance(persona, Alumno):
        claims["alumno_id"] = persona.alumno_id
    elif isinstance(persona, Profesor):
        claims["profesor_id"] = persona.profesor_id
    return jwt.encode(claims, llave, algorithm=ALGORITMO)


def persona_desde_token(token: str, llave: str) -> Persona:
    """Valida el token y arma la Persona. Cualquier problema -> 401 (sin decir cuál).

    No se le dice al cliente si el token venció, si la firma es falsa o si le falta
    un dato: esa pista solo le sirve a quien intenta falsificarlo.
    """
    try:
        claims = jwt.decode(
            token, llave,
            algorithms=[ALGORITMO],   # lista fija: un token con alg "none" u otro se rechaza
            options={"require": list(CLAIMS_OBLIGATORIOS)},
        )
        return _persona_de(claims)
    # InvalidTokenError: firma, vencido, mal formado, alg distinto, falta un claim.
    # KeyError/ValueError/TypeError: claims con tipos o valores que Persona no acepta.
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise NO_AUTENTICADO from None


def _persona_de(claims: dict[str, Any]) -> Persona:
    """Arma la subclase correcta. Los constructores de Persona validan ids y correo."""
    if not isinstance(claims["sub"], str) or not claims["sub"].isdigit():
        raise ValueError("sub debe ser el usuario_id en texto")
    usuario_id = int(claims["sub"])
    correo = claims["correo"]
    centro = claims.get("centro")
    match Rol(claims["rol"]):
        case Rol.ALUMNO:
            return Alumno(usuario_id, correo, claims["alumno_id"], centro)
        case Rol.PROFESOR:
            return Profesor(usuario_id, correo, claims["profesor_id"], centro)
        case Rol.ADMINISTRADOR:
            return Administrador(usuario_id, correo, centro)


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
