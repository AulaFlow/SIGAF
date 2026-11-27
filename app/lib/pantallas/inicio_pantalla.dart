import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../repositorios/alumno_repositorio.dart';
import '../servicios/sesion.dart';
import '../widgets/estado.dart';
import 'lista_pantalla.dart';

const azul = Color(0xFF4F46E5);
const oscuro = Color(0xFF0F172A);
const violeta = Color(0xFF9333EA);
const cian = Color(0xFF0891B2);
const verde = Color(0xFF059669);
const naranja = Color(0xFFF59E0B);
const fondo = Color(0xFFF1F5F9);

class InicioPantalla extends StatefulWidget {
  const InicioPantalla({super.key});

  @override
  State<InicioPantalla> createState() => _InicioState();
}

class _InicioState extends State<InicioPantalla> {
  int index = 0;
  int revision = 0;

  static const labels = ['Inicio', 'Boleta', 'Pendientes'];

  static const icons = [
    Icons.dashboard_rounded,
    Icons.bar_chart_rounded,
    Icons.assignment_rounded,
  ];

  void navegar(int i) {
    if (i == index) return;

    setState(() {
      index = i;
      revision++;
    });
  }

  Future<void> cerrarSesion() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.logout_rounded, color: azul, size: 40),
        title: const Text('Cerrar sesión'),
        content: const Text('¿Estás seguro de que deseas salir de SIGAF?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cerrar sesión'),
          ),
        ],
      ),
    );

    if (confirmar == true && mounted) {
      await context.read<Sesion>().salir();
    }
  }

  Widget menuLateral(bool extendido) {
    return Container(
      width: extendido ? 245 : 110,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF0F172A), Color(0xFF25215B)],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 24),

            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [azul, violeta]),
                borderRadius: BorderRadius.circular(18),
              ),
              child: const Icon(
                Icons.school_rounded,
                color: Colors.white,
                size: 30,
              ),
            ),

            const SizedBox(height: 12),

            if (extendido) ...[
              const Text(
                'SIGAF',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 25,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 2,
                ),
              ),
              const Text(
                'Portal académico',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
              ),
            ],

            const SizedBox(height: 35),

            if (extendido)
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 24),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'MENÚ PRINCIPAL',
                    style: TextStyle(
                      color: Color(0xFF94A3B8),
                      fontSize: 11,
                      letterSpacing: 1.5,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),

            const SizedBox(height: 12),

            Expanded(
              child: NavigationRail(
                backgroundColor: Colors.transparent,
                extended: extendido,
                minExtendedWidth: 225,
                minWidth: 110,
                selectedIndex: index,
                useIndicator: true,
                indicatorColor: azul,
                selectedIconTheme: const IconThemeData(color: Colors.white),
                unselectedIconTheme: const IconThemeData(
                  color: Color(0xFFCBD5E1),
                ),
                selectedLabelTextStyle: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
                unselectedLabelTextStyle: const TextStyle(
                  color: Color(0xFFCBD5E1),
                ),
                labelType: extendido
                    ? NavigationRailLabelType.none
                    : NavigationRailLabelType.all,
                onDestinationSelected: navegar,
                destinations: [
                  for (int i = 0; i < labels.length; i++)
                    NavigationRailDestination(
                      icon: Icon(icons[i]),
                      label: Text(
                        labels[i],
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(12),
              child: extendido
                  ? TextButton.icon(
                      onPressed: cerrarSesion,
                      icon: const Icon(
                        Icons.logout_rounded,
                        color: Color(0xFFFCA5A5),
                      ),
                      label: const Text(
                        'Cerrar sesión',
                        style: TextStyle(color: Color(0xFFFCA5A5)),
                      ),
                    )
                  : IconButton(
                      tooltip: 'Cerrar sesión',
                      onPressed: cerrarSesion,
                      icon: const Icon(
                        Icons.logout_rounded,
                        color: Color(0xFFFCA5A5),
                      ),
                    ),
            ),

            if (extendido)
              const Padding(
                padding: EdgeInsets.only(bottom: 18),
                child: Text(
                  '© 2026 AulaFlow',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget encabezado(bool computadora) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
      ),
      child: Row(
        children: [
          if (!computadora) ...[
            const Icon(Icons.school_rounded, color: azul, size: 28),
            const SizedBox(width: 10),
          ],

          Expanded(
            child: Text(
              computadora ? labels[index] : 'SIGAF',
              style: const TextStyle(
                color: oscuro,
                fontSize: 21,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),

          if (demo)
            const Padding(
              padding: EdgeInsets.only(right: 10),
              child: Text(
                'Demo',
                style: TextStyle(color: Color(0xFF64748B), fontSize: 11),
              ),
            ),

          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFFEEF2FF),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.person_rounded, color: azul),
          ),

          if (computadora) ...[
            const SizedBox(width: 10),
            const Text(
              'Estudiante',
              style: TextStyle(color: oscuro, fontWeight: FontWeight.w600),
            ),
          ] else
            IconButton(
              tooltip: 'Cerrar sesión',
              onPressed: cerrarSesion,
              icon: const Icon(Icons.logout_rounded),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final computadora = constraints.maxWidth >= 600;
        final extendido = constraints.maxWidth >= 1050;

        final Widget pagina;

        switch (index) {
          case 1:
            pagina = ListaPantalla(
              key: ValueKey('boleta-$revision'),
              boleta: true,
            );
            break;

          case 2:
            pagina = ListaPantalla(
              key: ValueKey('pendientes-$revision'),
              boleta: false,
            );
            break;

          default:
            pagina = PanelAlumno(
              key: ValueKey('inicio-$revision'),
              onNavigate: navegar,
            );
        }

        final contenido = Column(
          children: [
            encabezado(computadora),
            Expanded(child: pagina),
          ],
        );

        return Scaffold(
          backgroundColor: fondo,
          body: computadora
              ? Row(
                  children: [
                    menuLateral(extendido),
                    Expanded(child: contenido),
                  ],
                )
              : SafeArea(child: contenido),
          bottomNavigationBar: computadora
              ? null
              : NavigationBar(
                  backgroundColor: Colors.white,
                  indicatorColor: const Color(0xFFE0E7FF),
                  selectedIndex: index,
                  onDestinationSelected: navegar,
                  destinations: [
                    for (int i = 0; i < labels.length; i++)
                      NavigationDestination(
                        icon: Icon(icons[i]),
                        label: labels[i],
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class DatosPanel {
  final Map<String, dynamic> alumno;
  final Resultado boleta;
  final Resultado pendientes;

  DatosPanel(this.alumno, this.boleta, this.pendientes);

  double? get promedio {
    final notas = boleta.items
        .map(
          (m) =>
              double.tryParse('${m['final'] ?? m['promedio_parciales'] ?? ''}'),
        )
        .whereType<double>()
        .toList();

    if (notas.isEmpty) return null;

    return notas.reduce((a, b) => a + b) / notas.length;
  }
}

class PanelAlumno extends StatefulWidget {
  final ValueChanged<int>? onNavigate;

  const PanelAlumno({super.key, this.onNavigate});

  @override
  State<PanelAlumno> createState() => _PanelState();
}

class _PanelState extends State<PanelAlumno> {
  late Future<DatosPanel> datos;

  @override
  void initState() {
    super.initState();
    datos = cargar();
  }

  Future<DatosPanel> cargar() async {
    final repo = context.read<AlumnoRepositorio>();

    final boleta = await repo.boleta();
    final pendientes = await repo.pendientes();

    Map<String, dynamic> alumno;

    try {
      alumno = await repo.datos();
    } catch (_) {
      if (!boleta.offline && !pendientes.offline) {
        rethrow;
      }
      alumno = {'nombre': 'Estudiante'};
    }

    return DatosPanel(alumno, boleta, pendientes);
  }

  void recargar() {
    setState(() {
      datos = cargar();
    });
  }

  String fechaActual() {
    final hoy = DateTime.now();

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

    return '${hoy.day} de ${meses[hoy.month - 1]}, ${hoy.year}';
  }

  Widget bienvenida(DatosPanel panel) {
    final nombre = panel.alumno['nombre'] ?? 'Estudiante';

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF312E81), azul, violeta],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x264F46E5),
            blurRadius: 25,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Stack(
          children: [
            Positioned(
              right: -50,
              top: -70,
              child: Container(
                height: 230,
                width: 230,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0x20FFFFFF),
                ),
              ),
            ),

            Positioned(
              right: 90,
              bottom: -80,
              child: Container(
                height: 180,
                width: 180,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0x15FFFFFF),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(28),
              child: LayoutBuilder(
                builder: (context, constraints) {
                  return Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 7,
                              ),
                              decoration: BoxDecoration(
                                color: const Color(0x25FFFFFF),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: const Text(
                                'TU ESPACIO ACADÉMICO',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1,
                                ),
                              ),
                            ),

                            const SizedBox(height: 16),

                            Text(
                              '¡Hola, $nombre!',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 32,
                                fontWeight: FontWeight.w900,
                              ),
                            ),

                            const SizedBox(height: 10),

                            const Text(
                              'Consulta tu progreso, organiza tus '
                              'actividades y alcanza tus metas.',
                              style: TextStyle(
                                color: Color(0xFFE0E7FF),
                                fontSize: 15,
                                height: 1.6,
                              ),
                            ),

                            const SizedBox(height: 20),

                            Row(
                              children: [
                                const Icon(
                                  Icons.calendar_today_outlined,
                                  color: Color(0xFFDDD6FE),
                                  size: 16,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    fechaActual(),
                                    style: const TextStyle(
                                      color: Color(0xFFDDD6FE),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),

                      if (constraints.maxWidth > 500)
                        const Padding(
                          padding: EdgeInsets.only(left: 24),
                          child: Icon(
                            Icons.school_rounded,
                            color: Color(0xFFC4B5FD),
                            size: 125,
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget estadistica({
    required String titulo,
    required String valor,
    required String subtitulo,
    required IconData icono,
    required Color color,
    required VoidCallback accion,
  }) {
    return Card(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      child: InkWell(
        onTap: accion,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icono, color: color, size: 27),
              ),

              const SizedBox(height: 16),

              Text(
                valor,
                style: TextStyle(
                  fontSize: 36,
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
              ),

              const SizedBox(height: 4),

              Text(
                titulo,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: oscuro,
                ),
              ),

              const SizedBox(height: 5),

              Text(
                subtitulo,
                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget accesoRapido({
    required String titulo,
    required String descripcion,
    required IconData icono,
    required Color color,
    required Color colorFondo,
    required VoidCallback accion,
  }) {
    return Material(
      color: colorFondo,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: accion,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icono, color: Colors.white, size: 26),
              ),

              const SizedBox(width: 14),

              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      titulo,
                      style: const TextStyle(
                        color: oscuro,
                        fontSize: 17,
                        fontWeight: FontWeight.bold,
                      ),
                    ),

                    const SizedBox(height: 5),

                    Text(
                      descripcion,
                      style: const TextStyle(
                        fontSize: 13,
                        color: Color(0xFF475569),
                      ),
                    ),
                  ],
                ),
              ),

              Icon(Icons.arrow_forward_rounded, color: color),
            ],
          ),
        ),
      ),
    );
  }

  Widget tituloSeccion(String titulo, String subtitulo) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          titulo,
          style: const TextStyle(
            fontSize: 23,
            fontWeight: FontWeight.bold,
            color: oscuro,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          subtitulo,
          style: const TextStyle(fontSize: 14, color: Color(0xFF64748B)),
        ),
      ],
    );
  }

  Widget tarjetaTarea(Map<String, dynamic> tarea) {
    final fecha = DateTime.tryParse('${tarea['fecha_limite'] ?? ''}')
        ?.toLocal();
    final ahora = DateTime.now();

    final cierre = DateTime.tryParse('${tarea['cierre_entrega'] ?? ''}')
        ?.toLocal();

    final cerrada = cierre != null && ahora.isAfter(cierre);
    final fechaPasada = fecha != null && ahora.isAfter(fecha);
    final tardia =
        tarea['solo_tardia'] == true ||
        (fechaPasada && cierre != null && !cerrada);
    final vencida = cerrada || (fechaPasada && !tardia);

    final estado = cerrada
        ? 'Entrega cerrada'
        : tardia
        ? 'Entrega tardía'
        : vencida
        ? 'Fecha vencida'
        : 'Pendiente';

    final color = vencida ? Colors.red : naranja;

    final fechaTexto = fecha == null
        ? '${tarea['fecha_limite'] ?? 'Sin fecha'}'
        : '${fecha.day.toString().padLeft(2, '0')}/'
              '${fecha.month.toString().padLeft(2, '0')}/'
              '${fecha.year}';

    return Card(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 10,
        ),
        leading: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFEEF2FF),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.assignment_outlined, color: azul),
        ),

        title: Text(
          '${tarea['titulo'] ?? 'Actividad'}',
          style: const TextStyle(fontWeight: FontWeight.bold, color: oscuro),
        ),

        subtitle: Text(
          '${tarea['materia'] ?? ''}\n$fechaTexto',
          style: const TextStyle(color: Color(0xFF64748B)),
        ),

        isThreeLine: true,

        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            estado,
            style: TextStyle(
              color: vencida ? Colors.red.shade700 : const Color(0xFFB45309),
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),

        onTap: () => widget.onNavigate?.call(2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<DatosPanel>(
      future: datos,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator(color: azul));
        }

        if (snapshot.hasError) {
          return MensajeError(texto: '${snapshot.error}', reintentar: recargar);
        }

        final panel = snapshot.data!;

        return RefreshIndicator(
          onRefresh: () async {
            recargar();
            try {
              await datos;
            } catch (_) {
              // FutureBuilder mostrará el error.
            }
          },
          child: LayoutBuilder(
            builder: (context, constraints) {
              final ancho = constraints.maxWidth;
              final padding = ancho > 700 ? 28.0 : 16.0;

              final disponible = ancho - padding * 2;

              final columnas = disponible >= 720
                  ? 3
                  : disponible >= 450
                  ? 2
                  : 1;

              final anchoTarjeta =
                  (disponible - (columnas - 1) * 16) / columnas;

              final anchoAcceso = disponible >= 600
                  ? (disponible - 16) / 2
                  : disponible;

              final tareas = [...panel.pendientes.items];

              tareas.sort(
                (a, b) => '${a['fecha_limite'] ?? ''}'.compareTo(
                  '${b['fecha_limite'] ?? ''}',
                ),
              );

              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.all(padding),
                children: [
                  bienvenida(panel),

                  if (panel.boleta.offline || panel.pendientes.offline) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFF7ED),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.cloud_off_rounded, color: naranja),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Sin conexión. Mostrando datos guardados.',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(height: 28),

                  tituloSeccion(
                    'Resumen académico',
                    'Tu información más importante.',
                  ),

                  const SizedBox(height: 16),

                  Wrap(
                    spacing: 16,
                    runSpacing: 16,
                    children: [
                      SizedBox(
                        width: anchoTarjeta,
                        child: estadistica(
                          titulo: 'Promedio general',
                          valor: panel.promedio?.toStringAsFixed(1) ?? '—',
                          subtitulo: 'Según tu boleta',
                          icono: Icons.trending_up_rounded,
                          color: azul,
                          accion: () => widget.onNavigate?.call(1),
                        ),
                      ),

                      SizedBox(
                        width: anchoTarjeta,
                        child: estadistica(
                          titulo: 'Materias',
                          valor: '${panel.boleta.items.length}',
                          subtitulo: 'Materias en tu boleta',
                          icono: Icons.menu_book_rounded,
                          color: cian,
                          accion: () => widget.onNavigate?.call(1),
                        ),
                      ),

                      SizedBox(
                        width: anchoTarjeta,
                        child: estadistica(
                          titulo: 'Tareas pendientes',
                          valor: '${panel.pendientes.items.length}',
                          subtitulo: 'Actividades por realizar',
                          icono: Icons.pending_actions_rounded,
                          color: naranja,
                          accion: () => widget.onNavigate?.call(2),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 30),

                  tituloSeccion(
                    'Accesos rápidos',
                    'Encuentra lo que necesitas.',
                  ),

                  const SizedBox(height: 16),

                  Wrap(
                    spacing: 16,
                    runSpacing: 16,
                    children: [
                      SizedBox(
                        width: anchoAcceso,
                        child: accesoRapido(
                          titulo: 'Calificaciones',
                          descripcion: 'Consulta tu boleta',
                          icono: Icons.bar_chart_rounded,
                          color: violeta,
                          colorFondo: const Color(0xFFF3E8FF),
                          accion: () => widget.onNavigate?.call(1),
                        ),
                      ),

                      SizedBox(
                        width: anchoAcceso,
                        child: accesoRapido(
                          titulo: 'Actividades',
                          descripcion: 'Revisa y entrega tareas',
                          icono: Icons.assignment_turned_in,
                          color: verde,
                          colorFondo: const Color(0xFFD1FAE5),
                          accion: () => widget.onNavigate?.call(2),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 30),

                  Row(
                    children: [
                      Expanded(
                        child: tituloSeccion(
                          'Próximas actividades',
                          'Mantente al día con tus entregas.',
                        ),
                      ),
                      IconButton(
                        tooltip: 'Actualizar',
                        onPressed: recargar,
                        icon: const Icon(Icons.refresh_rounded, color: azul),
                      ),
                    ],
                  ),

                  const SizedBox(height: 16),

                  if (tareas.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(25),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: const Column(
                        children: [
                          Icon(
                            Icons.check_circle_outline,
                            color: verde,
                            size: 48,
                          ),
                          SizedBox(height: 12),
                          Text(
                            '¡Estás al corriente!',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          SizedBox(height: 5),
                          Text('No tienes actividades pendientes.'),
                        ],
                      ),
                    ),

                  for (final tarea in tareas.take(3)) tarjetaTarea(tarea),

                  if (tareas.isNotEmpty)
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: () => widget.onNavigate?.call(2),
                        icon: const Icon(Icons.arrow_forward_rounded),
                        label: const Text('Ver todas las actividades'),
                      ),
                    ),

                  const SizedBox(height: 24),

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
