import pytest

from app.dominio.personas import Administrador, Alumno, Persona, Profesor, Rol


def test_persona_es_abstracta():
    with pytest.raises(TypeError):
        Persona(1, "a@sigaf.test")  # type: ignore[abstract]


def test_alumno_pone_su_id_en_la_sesion():
    alumno = Alumno(10, "alumno@sigaf.test", alumno_id=7)
    assert alumno.rol is Rol.ALUMNO
    assert alumno.alumno_id == 7
    assert alumno.variables_de_sesion() == {"sigaf.alumno_sesion": "7"}


def test_profesor_y_admin_no_ponen_variables():
    profesor = Profesor(2, "profe@sigaf.test", profesor_id=3)
    admin = Administrador(1, "admin@sigaf.test")
    assert profesor.rol is Rol.PROFESOR and profesor.profesor_id == 3
    assert admin.rol is Rol.ADMINISTRADOR
    assert profesor.variables_de_sesion() == {} == admin.variables_de_sesion()


def test_polimorfismo_misma_llamada_distinto_resultado():
    personas: list[Persona] = [
        Alumno(1, "a@sigaf.test", 5),
        Profesor(2, "p@sigaf.test", 6),
        Administrador(3, "x@sigaf.test"),
    ]
    assert [p.rol.value for p in personas] == ["alumno", "profesor", "administrador"]


def test_es_revisa_roles():
    profesor = Profesor(2, "p@sigaf.test", 6)
    assert profesor.es(Rol.PROFESOR, Rol.ADMINISTRADOR)
    assert not profesor.es(Rol.ALUMNO)


@pytest.mark.parametrize("valor", [0, -1, True, "5", 2.0])
def test_ids_invalidos(valor):
    with pytest.raises(ValueError):
        Alumno(1, "a@sigaf.test", alumno_id=valor)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Administrador(valor, "a@sigaf.test")  # type: ignore[arg-type]


def test_correo_invalido():
    with pytest.raises(ValueError):
        Profesor(1, "sin-arroba", 2)


def test_encapsulamiento_y_repr_sin_correo():
    alumno = Alumno(10, "privado@sigaf.test", 7)
    with pytest.raises(AttributeError):
        alumno.alumno_id = 99  # type: ignore[misc]
    assert repr(alumno) == "Alumno(usuario_id=10)"
