-- =====================================================================
-- SIGAF · db/pruebas_seguridad.sql  (issue #6)
-- Comprueba que cada rol solo puede hacer lo que le toca, y que el cifrado
-- y la seudonimización funcionan. Correr DESPUÉS de pruebas.sql.
-- Se ejecuta como superusuario y cambia de rol con SET ROLE.
-- =====================================================================
SET search_path TO sigaf, public;
SELECT set_config('sigaf.llave_datos',     'llave-de-prueba-datos-0123456789abcdef', false),
       set_config('sigaf.llave_seudonimo', 'llave-de-prueba-seudonimo-0123456789ab', false) \gset
\echo '== Pruebas de seguridad =='

-- Ayuda: ¿el rol puede ejecutar esta sentencia?
CREATE OR REPLACE FUNCTION pg_temp.puede(p_rol TEXT, p_sql TEXT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE format('SET LOCAL ROLE %I', p_rol);
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN insufficient_privilege THEN
        RESET ROLE;
        RETURN FALSE;
    END;
    RESET ROLE;
    RETURN TRUE;
END $$;

-- S1. Cifrado en reposo: la tabla no contiene el nombre en claro
DO $$
BEGIN
    ASSERT NOT EXISTS (SELECT 1 FROM alumno_datos_personales
                       WHERE position(convert_to('Pérez', 'UTF8') IN apellidos_cifrado) > 0),
        'el apellido aparece en claro';
    ASSERT (SELECT apellidos FROM fn_datos_alumno(1)) = 'Pérez Luna', 'no descifra con la llave correcta';
    RAISE NOTICE 'S1 OK: nombre y apellidos guardados cifrados (AES-256)';
END $$;

-- S2. Sin llave (o con otra llave) no se puede descifrar
DO $$
BEGIN
    PERFORM set_config('sigaf.llave_datos', '', false);
    BEGIN
        PERFORM * FROM fn_datos_alumno(1);
        RAISE EXCEPTION 'S2 FALLÓ: descifró sin llave';
    EXCEPTION WHEN invalid_authorization_specification THEN
        RAISE NOTICE 'S2a OK: sin llave -> %', SQLERRM;
    END;
    PERFORM set_config('sigaf.llave_datos', 'otra-llave-incorrecta-0123456789abcdef', false);
    BEGIN
        PERFORM * FROM fn_datos_alumno(1);
        RAISE EXCEPTION 'S2 FALLÓ: descifró con otra llave';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'S2 FALLÓ%' THEN RAISE; END IF;
        RAISE NOTICE 'S2b OK: con llave incorrecta -> %', SQLERRM;
    WHEN external_routine_invocation_exception OR data_exception THEN
        RAISE NOTICE 'S2b OK: con llave incorrecta -> %', SQLERRM;
    END;
    PERFORM set_config('sigaf.llave_datos', 'llave-de-prueba-datos-0123456789abcdef', false);
END $$;

-- S3. Seudonimización: 64 caracteres, determinista, no contiene la matrícula
DO $$
DECLARE v1 TEXT; v2 TEXT;
BEGIN
    v1 := fn_seudonimizar('A000001');
    ASSERT length(v1) = 64 AND v1 = fn_seudonimizar(' a000001 '), 'no es determinista';
    ASSERT position('A000001' IN v1) = 0, 'el seudónimo contiene la matrícula';
    ASSERT EXISTS (SELECT 1 FROM alumno WHERE matricula = v1), 'el inicio de sesión no encontraría al alumno';
    PERFORM set_config('sigaf.llave_seudonimo', 'otra-llave-de-seudonimo-0123456789ab', false);
    v2 := fn_seudonimizar('A000001');
    PERFORM set_config('sigaf.llave_seudonimo', 'llave-de-prueba-seudonimo-0123456789ab', false);
    ASSERT v1 <> v2, 'otra llave dio el mismo seudónimo';
    RAISE NOTICE 'S3 OK: seudónimo HMAC de 64 caracteres, depende de la llave';
END $$;

-- S4. API: no lee datos personales directo, pero sí por la función del profesor
DO $$
BEGIN
    ASSERT NOT pg_temp.puede('sigaf_api', 'SELECT * FROM sigaf.alumno_datos_personales'),
        'la API leyó datos personales directo';
    ASSERT pg_temp.puede('sigaf_api', 'SELECT * FROM sigaf.fn_alumnos_de_profesor(1)'),
        'la API no pudo usar la función del profesor';
    ASSERT NOT pg_temp.puede('sigaf_api', 'SELECT * FROM sigaf.fn_datos_alumno(1)'),
        'la API usó la función de administrador';
    RAISE NOTICE 'S4 OK: la API solo ve nombres por fn_alumnos_de_profesor';
END $$;

-- S5. El profesor solo ve alumnos de SUS grupos
DO $$
BEGIN
    INSERT INTO usuario (correo, hash_contrasena, rol_id) VALUES ('profe2@sigaf.test', '$2b$12$hashDeEjemploNoReal', 2);
    INSERT INTO profesor (usuario_id, centro_academico_id, num_empleado, nombre, apellidos)
    VALUES (currval('usuario_usuario_id_seq'), 1, 'E-0002', 'Pablo', 'Núñez Lara');
    ASSERT (SELECT count(*) FROM fn_alumnos_de_profesor(1)) = 2, 'el profesor 1 debe ver a sus 2 alumnos';
    ASSERT (SELECT count(*) FROM fn_alumnos_de_profesor(currval('profesor_profesor_id_seq'))) = 0,
        'un profesor sin grupos vio alumnos';
    RAISE NOTICE 'S5 OK: un profesor sin esos grupos no ve a esos alumnos';
END $$;

-- S6. API: califica, pero no toca la bitácora, no borra y no cambia el directorio
DO $$
DECLARE v_antes INT := (SELECT count(*) FROM bitacora_calificacion);
BEGIN
    ASSERT pg_temp.puede('sigaf_api',
        'UPDATE sigaf.calificacion SET valor = 6 WHERE inscripcion_id = 1 AND tipo = ''parcial1'''),
        'la API no pudo calificar';
    ASSERT (SELECT count(*) FROM bitacora_calificacion) = v_antes + 1, 'el cambio no quedó en la bitácora';
    ASSERT NOT pg_temp.puede('sigaf_api', 'DELETE FROM sigaf.bitacora_calificacion'), 'la API borró la bitácora';
    ASSERT NOT pg_temp.puede('sigaf_api', 'UPDATE sigaf.bitacora_calificacion SET valor_nuevo = 10'),
        'la API alteró la bitácora';
    ASSERT NOT pg_temp.puede('sigaf_api', 'DELETE FROM sigaf.calificacion'), 'la API borró calificaciones';
    ASSERT NOT pg_temp.puede('sigaf_api', 'UPDATE sigaf.directorio_fragmento SET fragmento = ''B'''),
        'la API cambió el directorio';
    RAISE NOTICE 'S6 OK: la API califica y queda rastro, pero no puede borrar ni alterar la bitácora';
END $$;

-- S7. ETL: solo lectura de lo académico
DO $$
BEGIN
    ASSERT pg_temp.puede('sigaf_etl', 'SELECT count(*) FROM sigaf.calificacion'), 'el ETL no lee calificaciones';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT * FROM sigaf.usuario'), 'el ETL leyó usuarios';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT * FROM sigaf.alumno_datos_personales'), 'el ETL leyó datos personales';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT nombre FROM sigaf.profesor'), 'el ETL leyó nombres de profesores';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT * FROM sigaf.mensaje'), 'el ETL leyó mensajes';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT * FROM sigaf.fn_alumnos_de_profesor(1)'),
        'el ETL descifró nombres';
    ASSERT NOT pg_temp.puede('sigaf_etl',
        'UPDATE sigaf.calificacion SET valor = 10 WHERE calificacion_id = 1'), 'el ETL escribió';
    RAISE NOTICE 'S7 OK: el ETL solo lee datos académicos, sin datos personales';
END $$;

-- S8. Un usuario cualquiera (PUBLIC) no ve nada del esquema
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_prueba_publico') THEN
        CREATE ROLE sigaf_prueba_publico NOLOGIN;
    END IF;
    ASSERT NOT pg_temp.puede('sigaf_prueba_publico', 'SELECT * FROM sigaf.alumno'), 'PUBLIC leyó alumnos';
    ASSERT NOT pg_temp.puede('sigaf_prueba_publico', 'SELECT sigaf.fn_seudonimizar(''x'')'),
        'PUBLIC usó funciones de llaves';
    DROP ROLE sigaf_prueba_publico;
    RAISE NOTICE 'S8 OK: un rol sin permisos no ve nada del esquema';
END $$;

-- S9. El alumno ve SUS datos personales y los de nadie más
DO $$
BEGIN
    BEGIN
        PERFORM * FROM fn_mis_datos();
        RAISE EXCEPTION 'S9 FALLÓ: devolvió datos sin alumno en la sesión';
    EXCEPTION WHEN invalid_authorization_specification THEN
        RAISE NOTICE 'S9a OK: sin alumno autenticado -> %', SQLERRM;
    END;
    PERFORM set_config('sigaf.alumno_sesion', '1', false);
    ASSERT (SELECT count(*) FROM fn_mis_datos()) = 1, 'debe devolver solo un alumno';
    ASSERT (SELECT apellidos FROM fn_mis_datos()) = 'Pérez Luna', 'no devolvió sus propios datos';
    ASSERT NOT EXISTS (SELECT 1 FROM fn_mis_datos() WHERE alumno_id <> 1), 'devolvió datos de otro alumno';
    PERFORM set_config('sigaf.alumno_sesion', '2', false);
    ASSERT (SELECT apellidos FROM fn_mis_datos()) = 'Soto Vega', 'el alumno 2 no vio los suyos';
    ASSERT pg_temp.puede('sigaf_api', 'SELECT * FROM sigaf.fn_mis_datos()'), 'la API no puede usarla';
    ASSERT NOT pg_temp.puede('sigaf_etl', 'SELECT * FROM sigaf.fn_mis_datos()'), 'el ETL la usó';
    PERFORM set_config('sigaf.alumno_sesion', '', false);
    RAISE NOTICE 'S9b OK: cada alumno ve solo sus propios datos personales';
END $$;

\echo '== Todas las pruebas de seguridad pasaron =='
