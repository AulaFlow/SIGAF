import 'alumno_repositorio.dart';

class AlumnoRepoFalso implements AlumnoRepositorio {
  final tareas = <Map<String, dynamic>>[
    {
      'tarea_id': 57,
      'titulo': 'Práctica SQLite',
      'materia': 'Programación móvil',
      'fecha_limite': '2026-11-27',
      'solo_tardia': false,
    },
    {
      'tarea_id': 58,
      'titulo': 'Reporte de laboratorio',
      'materia': 'Circuitos eléctricos',
      'fecha_limite': '2026-12-01',
      'solo_tardia': false,
    },
  ];
  @override
  Future<Map<String, dynamic>> datos() async => {
    'nombre': 'Alumno',
    'apellidos': 'de prueba',
  };
  @override
  Future<Resultado> boleta() async => Resultado([
    {
      'inscripcion_id': 1,
      'materia': 'Programación móvil',
      'parcial1': 9,
      'parcial2': 8,
      'parcial3': 10,
      'promedio_parciales': 9,
      'final': 9,
    },
    {
      'inscripcion_id': 2,
      'materia': 'Bases de datos distribuidas',
      'parcial1': 8,
      'parcial2': 9,
      'parcial3': 9,
      'promedio_parciales': 8.67,
      'final': 9,
    },
  ]);
  @override
  Future<Resultado> pendientes() async => Resultado(List.of(tareas));
  @override
  Future<Map<String, dynamic>> entregar(
    String id,
    Map<String, dynamic> archivo,
  ) async {
    tareas.removeWhere((t) => t['tarea_id'].toString() == id);
    return {'entrega_id': 1, 'estado': 'simulada'};
  }
}
