import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../repositorios/alumno_repositorio.dart';
import '../widgets/estado.dart';
import 'entregar_pantalla.dart';

class ListaPantalla extends StatefulWidget {
  final bool boleta;

  const ListaPantalla({super.key, required this.boleta});

  @override
  State<ListaPantalla> createState() => _ListaState();
}

class _ListaState extends State<ListaPantalla> {
  static const azul = Color(0xFF4F46E5);
  static const violeta = Color(0xFF9333EA);
  static const oscuro = Color(0xFF0F172A);
  static const cian = Color(0xFF0891B2);
  static const verde = Color(0xFF059669);
  static const naranja = Color(0xFFEA580C);
  static const rojo = Color(0xFFDC2626);
  static const gris = Color(0xFF64748B);

  late Future<Resultado> futuro;

  Future<Resultado> cargar() {
    final repo = context.read<AlumnoRepositorio>();

    return widget.boleta ? repo.boleta() : repo.pendientes();
  }

  @override
  void initState() {
    super.initState();
    futuro = cargar();
  }

  void recargar() {
    setState(() {
      futuro = cargar();
    });
  }

  double? numero(dynamic valor) {
    return double.tryParse('${valor ?? ''}');
  }

  String formato(dynamic valor) {
    final n = numero(valor);

    if (n == null) return '—';

    if (n == n.roundToDouble()) {
      return n.toStringAsFixed(0);
    }

    return n.toStringAsFixed(2);
  }

  Color colorNota(dynamic valor) {
    final n = numero(valor);

    if (n == null) return gris;
    if (n >= 9) return verde;
    if (n >= 8) return azul;
    if (n >= 7) return cian;
    if (n >= 6) return naranja;

    return rojo;
  }

  double? promedioGeneral(List<Map<String, dynamic>> materias) {
    final notas = materias
        .map((m) => numero(m['final'] ?? m['promedio_parciales']))
        .whereType<double>()
        .toList();

    if (notas.isEmpty) return null;

    return notas.reduce((a, b) => a + b) / notas.length;
  }

  DateTime? fechaLimite(Map<String, dynamic> tarea) {
    return DateTime.tryParse('${tarea['fecha_limite'] ?? ''}')?.toLocal();
  }

  int? diasRestantes(Map<String, dynamic> tarea) {
    final fecha = fechaLimite(tarea);

    if (fecha == null) return null;

    final hoy = DateTime.now();

    final inicio = DateTime.utc(hoy.year, hoy.month, hoy.day);

    final limite = DateTime.utc(fecha.year, fecha.month, fecha.day);

    return limite.difference(inicio).inDays;
  }

  String fechaTexto(dynamic valor) {
    final fecha = DateTime.tryParse('${valor ?? ''}')?.toLocal();

    if (fecha == null) {
      return '${valor ?? 'Sin fecha asignada'}';
    }

    const meses = [
      'enero',
      'febrero',
      'marzo',
      'abril',
      'mayo',
      'junio',
      'julio',
      'agosto',
      'septiembre',
      'octubre',
      'noviembre',
      'diciembre',
    ];

    return '${fecha.day} de '
        '${meses[fecha.month - 1]} de '
        '${fecha.year}';
  }

  IconData iconoMateria(String nombre) {
    final texto = nombre.toLowerCase();

    if (texto.contains('datos')) {
      return Icons.storage_rounded;
    }

    if (texto.contains('móvil') || texto.contains('movil')) {
      return Icons.smartphone_rounded;
    }

    if (texto.contains('circuito')) {
      return Icons.electrical_services_rounded;
    }

    if (texto.contains('programación')) {
      return Icons.code_rounded;
    }

    if (texto.contains('estadística') || texto.contains('probabilidad')) {
      return Icons.analytics_rounded;
    }

    return Icons.menu_book_rounded;
  }

  Widget encabezado() {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.boleta
                    ? 'Boleta de calificaciones'
                    : 'Tareas pendientes',
                style: const TextStyle(
                  fontSize: 27,
                  fontWeight: FontWeight.w800,
                  color: oscuro,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                widget.boleta
                    ? 'Consulta tu rendimiento académico.'
                    : 'Organiza tus actividades y entregas.',
                style: const TextStyle(color: gris, fontSize: 14),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: IconButton(
            tooltip: 'Actualizar',
            onPressed: recargar,
            icon: const Icon(Icons.refresh_rounded, color: azul),
          ),
        ),
      ],
    );
  }

  Widget resumenBoleta(List<Map<String, dynamic>> materias) {
    final promedio = promedioGeneral(materias);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(26),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF312E81), azul, violeta],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x254F46E5),
            blurRadius: 24,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'PROMEDIO GENERAL',
                  style: TextStyle(
                    color: Color(0xFFDDD6FE),
                    fontSize: 12,
                    letterSpacing: 1.5,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      promedio?.toStringAsFixed(1) ?? '—',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 48,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const Text(
                      ' / 10',
                      style: TextStyle(color: Color(0xFFC4B5FD), fontSize: 22),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: LinearProgressIndicator(
                    value: promedio == null
                        ? 0
                        : (promedio / 10).clamp(0.0, 1.0).toDouble(),
                    minHeight: 9,
                    color: const Color(0xFFC4B5FD),
                    backgroundColor: const Color(0x35FFFFFF),
                  ),
                ),
                const SizedBox(height: 15),
                Text(
                  '${materias.length} materias registradas',
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0x22FFFFFF),
              borderRadius: BorderRadius.circular(24),
            ),
            child: const Icon(
              Icons.trending_up_rounded,
              color: Colors.white,
              size: 52,
            ),
          ),
        ],
      ),
    );
  }

  Widget tarjetaParcial(String titulo, dynamic valor) {
    final color = colorNota(valor);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 18),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.12)),
      ),
      child: Column(
        children: [
          Text(
            titulo,
            textAlign: TextAlign.center,
            style: const TextStyle(color: gris, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Text(
            formato(valor),
            style: TextStyle(
              color: color,
              fontSize: 28,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }

  Widget tarjetaMateria(Map<String, dynamic> materia, int index) {
    const colores = [azul, cian, violeta, verde, naranja];

    final color = colores[index % colores.length];

    final nombre = '${materia['materia'] ?? 'Materia'}';

    final promedio = numero(materia['promedio_parciales']);

    final notaFinal = materia['final'];
    final colorFinal = colorNota(notaFinal);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x080F172A),
            blurRadius: 15,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(15),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(iconoMateria(nombre), color: color, size: 30),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      nombre,
                      style: const TextStyle(
                        color: oscuro,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 5),
                    const Text(
                      'Evaluaciones parciales',
                      style: TextStyle(color: gris, fontSize: 12),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 15,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: colorFinal.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: Column(
                  children: [
                    Text(
                      formato(notaFinal),
                      style: TextStyle(
                        color: colorFinal,
                        fontSize: 30,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      'Final',
                      style: TextStyle(color: colorFinal, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 22),

          Row(
            children: [
              Expanded(child: tarjetaParcial('Parcial 1', materia['parcial1'])),
              const SizedBox(width: 10),
              Expanded(child: tarjetaParcial('Parcial 2', materia['parcial2'])),
              const SizedBox(width: 10),
              Expanded(child: tarjetaParcial('Parcial 3', materia['parcial3'])),
            ],
          ),

          const SizedBox(height: 22),

          Row(
            children: [
              const Expanded(
                child: Text(
                  'Promedio de parciales',
                  style: TextStyle(color: gris, fontSize: 13),
                ),
              ),
              Text(
                formato(promedio),
                style: TextStyle(
                  color: color,
                  fontWeight: FontWeight.bold,
                  fontSize: 17,
                ),
              ),
            ],
          ),

          const SizedBox(height: 10),

          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: promedio == null
                  ? 0
                  : (promedio / 10).clamp(0.0, 1.0).toDouble(),
              minHeight: 8,
              color: color,
              backgroundColor: const Color(0xFFE2E8F0),
            ),
          ),
        ],
      ),
    );
  }

  Widget resumenPendientes(List<Map<String, dynamic>> tareas) {
    final proximas = tareas.where((t) {
      final dias = diasRestantes(t);

      return dias != null && dias >= 0 && dias <= 3 && t['solo_tardia'] != true;
    }).length;

    return LayoutBuilder(
      builder: (context, constraints) {
        final ancho = constraints.maxWidth;

        final tarjetas = [
          tarjetaResumen(
            titulo: 'Actividades pendientes',
            valor: '${tareas.length}',
            icono: Icons.assignment_rounded,
            colores: const [azul, violeta],
          ),
          tarjetaResumen(
            titulo: 'Próximas a vencer',
            valor: '$proximas',
            icono: Icons.schedule_rounded,
            colores: const [Color(0xFFEA580C), Color(0xFFF59E0B)],
          ),
        ];

        if (ancho < 500) {
          return Column(
            children: [tarjetas[0], const SizedBox(height: 14), tarjetas[1]],
          );
        }

        return Row(
          children: [
            Expanded(child: tarjetas[0]),
            const SizedBox(width: 16),
            Expanded(child: tarjetas[1]),
          ],
        );
      },
    );
  }

  Widget tarjetaResumen({
    required String titulo,
    required String valor,
    required IconData icono,
    required List<Color> colores,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: colores,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  valor,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 42,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  titulo,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(
              color: const Color(0x25FFFFFF),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Icon(icono, color: Colors.white, size: 32),
          ),
        ],
      ),
    );
  }

  Future<void> entregar(Map<String, dynamic> tarea) async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => EntregarPantalla(tarea: tarea)),
    );

    if (ok == true && mounted) {
      recargar();
    }
  }

  Widget tarjetaTarea(Map<String, dynamic> tarea, bool offline) {
    final dias = diasRestantes(tarea);

    final tardia = tarea['solo_tardia'] == true;

    final cierre = DateTime.tryParse('${tarea['cierre_entrega'] ?? ''}');

    final cerrada = cierre != null && DateTime.now().isAfter(cierre);

    Color color = cian;
    String estado = 'Pendiente';
    String tiempo = 'Consulta la fecha de entrega';

    if (cerrada) {
      color = rojo;
      estado = 'Entrega cerrada';
      tiempo = 'El periodo de entrega terminó';
    } else if (tardia) {
      color = naranja;
      estado = 'Entrega tardía';
      tiempo = 'La entrega será registrada como tardía';
    } else if (dias != null) {
      if (dias < 0) {
        color = rojo;
        estado = 'Fecha vencida';
        tiempo = 'La fecha límite ha pasado';
      } else if (dias == 0) {
        color = rojo;
        estado = 'Vence hoy';
        tiempo = 'Entrega durante el día de hoy';
      } else if (dias <= 3) {
        color = naranja;
        estado = 'Próxima a vencer';
        tiempo = dias == 1 ? 'Queda 1 día' : 'Quedan $dias días';
      } else {
        tiempo = 'Quedan $dias días';
      }
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x080F172A),
            blurRadius: 15,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(height: 5, color: color),
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Icon(
                          Icons.description_rounded,
                          color: color,
                          size: 28,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${tarea['titulo'] ?? 'Actividad'}',
                              style: const TextStyle(
                                fontSize: 19,
                                color: oscuro,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              '${tarea['materia'] ?? ''}',
                              style: const TextStyle(color: gris, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 18),

                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 7,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      estado,
                      style: TextStyle(
                        color: color,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  const Divider(color: Color(0xFFE2E8F0)),

                  const SizedBox(height: 10),

                  Row(
                    children: [
                      const Icon(
                        Icons.calendar_today_outlined,
                        size: 18,
                        color: gris,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Fecha límite: '
                          '${fechaTexto(tarea['fecha_limite'])}',
                          style: const TextStyle(color: oscuro, fontSize: 13),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 12),

                  Row(
                    children: [
                      Icon(Icons.schedule_rounded, color: color, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          tiempo,
                          style: TextStyle(
                            color: color,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 22),

                  SizedBox(
                    width: double.infinity,
                    height: 49,
                    child: FilledButton.icon(
                      onPressed: offline || cerrada
                          ? null
                          : () => entregar(tarea),
                      style: FilledButton.styleFrom(
                        backgroundColor: azul,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(13),
                        ),
                      ),
                      icon: const Icon(Icons.upload_file_rounded),
                      label: Text(
                        offline
                            ? 'Sin conexión'
                            : cerrada
                            ? 'Entrega cerrada'
                            : 'Entregar tarea',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget avisoOffline(Resultado resultado) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7ED),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: const Color(0xFFFED7AA)),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_rounded, color: naranja, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Sin conexión · datos guardados',
                  style: TextStyle(
                    color: Color(0xFF9A3412),
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  'Última actualización: ${resultado.fecha}',
                  style: const TextStyle(color: naranja, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget estadoVacio() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(35),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFFD1FAE5),
              borderRadius: BorderRadius.circular(50),
            ),
            child: Icon(
              widget.boleta ? Icons.menu_book_rounded : Icons.task_alt_rounded,
              color: verde,
              size: 45,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            widget.boleta
                ? 'No hay calificaciones registradas'
                : '¡Estás al corriente!',
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: oscuro,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            widget.boleta
                ? 'Tus calificaciones aparecerán aquí.'
                : 'No tienes actividades pendientes.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: gris, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget tituloSeccion(String titulo) {
    return Text(
      titulo,
      style: const TextStyle(
        color: oscuro,
        fontSize: 22,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Resultado>(
      future: futuro,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator(color: azul));
        }

        if (snapshot.hasError) {
          return MensajeError(texto: '${snapshot.error}', reintentar: recargar);
        }

        final resultado = snapshot.data!;

        final items = [...resultado.items];

        if (!widget.boleta) {
          items.sort((a, b) {
            final fa = fechaLimite(a);
            final fb = fechaLimite(b);

            if (fa == null && fb == null) return 0;
            if (fa == null) return 1;
            if (fb == null) return -1;

            return fa.compareTo(fb);
          });
        }

        return RefreshIndicator(
          color: azul,
          onRefresh: () async {
            recargar();

            try {
              await futuro;
            } catch (_) {
              // FutureBuilder mostrará el error.
            }
          },
          child: LayoutBuilder(
            builder: (context, constraints) {
              final ancho = constraints.maxWidth;

              final padding = ancho >= 700 ? 28.0 : 16.0;

              final disponible = ancho - padding * 2;

              final columnas = disponible >= 850 ? 2 : 1;

              final anchoTarjeta =
                  (disponible - (columnas - 1) * 18) / columnas;

              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.all(padding),
                children: [
                  encabezado(),

                  const SizedBox(height: 24),

                  if (resultado.offline) ...[
                    avisoOffline(resultado),
                    const SizedBox(height: 20),
                  ],

                  if (widget.boleta)
                    resumenBoleta(items)
                  else
                    resumenPendientes(items),

                  const SizedBox(height: 28),

                  tituloSeccion(
                    widget.boleta ? 'Mis materias' : 'Mis actividades',
                  ),

                  const SizedBox(height: 16),

                  if (items.isEmpty)
                    estadoVacio()
                  else
                    Wrap(
                      spacing: 18,
                      runSpacing: 18,
                      children: [
                        for (int i = 0; i < items.length; i++)
                          SizedBox(
                            width: anchoTarjeta,
                            child: widget.boleta
                                ? tarjetaMateria(items[i], i)
                                : tarjetaTarea(items[i], resultado.offline),
                          ),
                      ],
                    ),

                  const SizedBox(height: 30),

                  const Center(
                    child: Text(
                      'SIGAF · Universidad Autónoma de Aguascalientes',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                    ),
                  ),
                ],
              );
            },
          ),
        );
      },
    );
  }
}
