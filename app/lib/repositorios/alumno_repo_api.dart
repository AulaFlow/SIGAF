import 'alumno_repositorio.dart';
import '../servicios/api_cliente.dart';
import '../servicios/almacen_local.dart';

class AlumnoRepoApi implements AlumnoRepositorio {
  final ApiCliente api;
  final AlmacenLocal local;
  AlumnoRepoApi(this.api, this.local);
  @override
  Future<Map<String, dynamic>> datos() async =>
      Map<String, dynamic>.from(await api.request('GET', '/alumno/datos'));
  Future<Resultado> cargar(String grupo, String llave) async {
    try {
      final r = await api.request('GET', '/alumno/$grupo');
      final items = (r as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      if (items.any((e) => e[llave] == null)) {
        throw ApiError(422, 'La API no devolvió $llave');
      }
      await local.guardar(grupo, items, llave);
      return Resultado(items);
    } on ApiError catch (e) {
      if (e.status != 0 && e.status != 503) rethrow;
      final c = await local.leer(grupo);
      if (c == null) rethrow;
      return Resultado(
        (c['items'] as List).map((e) => Map<String, dynamic>.from(e)).toList(),
        offline: true,
        fecha: c['fecha'] as String,
      );
    }
  }

  @override
  Future<Resultado> boleta() => cargar('boleta', 'inscripcion_id');
  @override
  Future<Resultado> pendientes() => cargar('pendientes', 'tarea_id');
  @override
  Future<Map<String, dynamic>> entregar(
    String id,
    Map<String, dynamic> archivo,
  ) async => Map<String, dynamic>.from(
    await api.request('POST', '/alumno/tareas/$id/entregas', archivo),
  );
}
