class Resultado {
  final List<Map<String, dynamic>> items;
  final bool offline;
  final String? fecha;
  Resultado(this.items, {this.offline = false, this.fecha});
}

abstract class AlumnoRepositorio {
  Future<Map<String, dynamic>> datos();
  Future<Resultado> boleta();
  Future<Resultado> pendientes();
  Future<Map<String, dynamic>> entregar(
    String id,
    Map<String, dynamic> archivo,
  );
}
