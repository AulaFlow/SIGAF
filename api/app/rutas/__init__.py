"""Capa HTTP de la API (issue #23).

Cada ruta solo une tres cosas que ya existen: la persona (seguridad.py), un servicio
(app/servicios) y los esquemas de entrada y salida (app/esquemas). Ninguna ruta escribe
SQL ni consultas a MongoDB.
"""

from .alumno import router as router_alumno
from .estadisticas import router as router_estadisticas
from .profesor import router as router_profesor

ROUTERS = (router_alumno, router_profesor, router_estadisticas)
