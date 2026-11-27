import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../servicios/camara.dart';
import '../repositorios/alumno_repositorio.dart';

class EntregarPantalla extends StatefulWidget {
  final Map<String, dynamic> tarea;

  const EntregarPantalla({super.key, required this.tarea});

  @override
  State<EntregarPantalla> createState() => _EntregaState();
}

class _EntregaState extends State<EntregarPantalla> {
  final cam = Camara();

  XFile? foto;
  Uint8List? imagen;

  bool ocupado = false;
  bool enviando = false;

  static const azul = Color(0xFF4F46E5);
  static const violeta = Color(0xFF9333EA);
  static const oscuro = Color(0xFF0F172A);
  static const cian = Color(0xFF0891B2);
  static const verde = Color(0xFF059669);
  static const gris = Color(0xFF64748B);
  static const rojo = Color(0xFFDC2626);
  static const fondo = Color(0xFFF1F5F9);

  bool get tieneCamara =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  void aviso(String texto, {bool error = false}) {
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(texto),
        backgroundColor: error ? rojo : verde,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Future<void> elegir(bool usarCamara) async {
    if (ocupado) return;

    setState(() => ocupado = true);

    try {
      final archivo = await cam.elegir(camara: usarCamara);

      if (archivo == null || !mounted) return;

      final bytes = await archivo.readAsBytes();

      final esPng =
          bytes.length > 4 &&
          bytes[0] == 137 &&
          bytes[1] == 80 &&
          bytes[2] == 78 &&
          bytes[3] == 71;

      final esJpg = bytes.length > 2 && bytes[0] == 255 && bytes[1] == 216;

      if (!esPng && !esJpg) {
        throw Exception('Selecciona una imagen JPG o PNG.');
      }

      if (!mounted) return;

      setState(() {
        foto = archivo;
        imagen = bytes;
      });

      aviso('Imagen seleccionada correctamente.');
    } catch (e) {
      aviso('$e', error: true);
    } finally {
      if (mounted) {
        setState(() => ocupado = false);
      }
    }
  }

  void eliminarFoto() {
    if (ocupado) return;

    setState(() {
      foto = null;
      imagen = null;
    });
  }

  String tamanoArchivo() {
    final bytes = imagen?.length ?? 0;

    if (bytes < 1024) {
      return '$bytes B';
    }

    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }

    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
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

  Future<void> confirmarEntrega() async {
    if (foto == null || ocupado) return;

    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        icon: Container(
          padding: const EdgeInsets.all(16),
          decoration: const BoxDecoration(
            color: Color(0xFFEEF2FF),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.send_rounded, color: azul, size: 36),
        ),
        title: const Text(
          'Confirmar entrega',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        content: Text(
          '¿Deseas registrar la evidencia de '
          '"${widget.tarea['titulo']}"?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: azul,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(context, true),
            icon: const Icon(Icons.check_rounded),
            label: const Text('Confirmar'),
          ),
        ],
      ),
    );

    if (confirmar == true && mounted) {
      await entregar();
    }
  }

  Future<void> entregar() async {
    if (foto == null || ocupado) return;

    final repo = context.read<AlumnoRepositorio>();

    setState(() {
      ocupado = true;
      enviando = true;
    });

    try {
      final id = widget.tarea['tarea_id'].toString();

      final meta = await cam.guardar(id, foto!);

      final resultado = await repo.entregar(id, meta);

      if (!mounted) return;

      await mostrarExito('${resultado['estado'] ?? 'Registrada'}');

      if (!mounted) return;

      Navigator.pop(context, true);
    } catch (e) {
      aviso('$e', error: true);
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
          enviando = false;
        });
      }
    }
  }

  Future<void> mostrarExito(String estado) async {
    final estadoVisible = switch (estado) {
      'a_tiempo' => 'A tiempo',
      'tardia' => 'Tardía',
      _ => estado,
    };
    final colorEstado = estado == 'tardia' ? const Color(0xFFB45309) : verde;
    final fondoEstado = estado == 'tardia'
        ? const Color(0xFFFFEDD5)
        : const Color(0xFFD1FAE5);

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: const BoxDecoration(
                color: Color(0xFFD1FAE5),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_rounded, color: verde, size: 60),
            ),

            const SizedBox(height: 22),

            Text(
              demo ? '¡Entrega de prueba registrada!' : '¡Entrega registrada!',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: oscuro,
                fontSize: 24,
                fontWeight: FontWeight.w900,
              ),
            ),

            const SizedBox(height: 12),

            Text(
              demo
                  ? 'La evidencia se procesó en el entorno '
                        'de pruebas.'
                  : 'Tu evidencia fue registrada correctamente.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: gris, height: 1.5),
            ),

            const SizedBox(height: 15),

            Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 10),
              decoration: BoxDecoration(
                color: fondoEstado,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                'Estado: $estadoVisible',
                style: TextStyle(
                  color: colorEstado,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),

            const SizedBox(height: 24),

            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: verde,
                  foregroundColor: Colors.white,
                ),
                onPressed: () => Navigator.pop(context),
                child: const Text('Continuar'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget encabezadoActividad() {
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
            color: Color(0x254F46E5),
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
              right: -45,
              top: -65,
              child: Container(
                width: 230,
                height: 230,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0x20FFFFFF),
                ),
              ),
            ),

            Positioned(
              right: 80,
              bottom: -80,
              child: Container(
                width: 180,
                height: 180,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0x15FFFFFF),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(26),
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
                                'ACTIVIDAD ACADÉMICA',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  letterSpacing: 1,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),

                            const SizedBox(height: 18),

                            Text(
                              '${widget.tarea['titulo'] ?? 'Actividad'}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 30,
                                fontWeight: FontWeight.w900,
                              ),
                            ),

                            const SizedBox(height: 8),

                            Text(
                              '${widget.tarea['materia'] ?? ''}',
                              style: const TextStyle(
                                color: Color(0xFFE0E7FF),
                                fontSize: 16,
                              ),
                            ),

                            const SizedBox(height: 20),

                            Row(
                              children: [
                                const Icon(
                                  Icons.calendar_today_outlined,
                                  color: Color(0xFFDDD6FE),
                                  size: 18,
                                ),

                                const SizedBox(width: 10),

                                Expanded(
                                  child: Text(
                                    'Fecha límite: '
                                    '${fechaTexto(widget.tarea['fecha_limite'])}',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 14,
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
                          padding: EdgeInsets.only(left: 20),
                          child: Icon(
                            Icons.assignment_rounded,
                            color: Color(0xFFC4B5FD),
                            size: 110,
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

  Widget tituloSeccion(String titulo, String descripcion) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          titulo,
          style: const TextStyle(
            color: oscuro,
            fontSize: 23,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          descripcion,
          style: const TextStyle(color: gris, fontSize: 14, height: 1.5),
        ),
      ],
    );
  }

  Widget espacioImagen() {
    if (imagen == null) {
      return Material(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: ocupado ? null : () => elegir(false),
          borderRadius: BorderRadius.circular(20),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 42),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFC7D2FE), width: 2),
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEDE9FE),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: const Icon(
                    Icons.add_photo_alternate_outlined,
                    color: azul,
                    size: 54,
                  ),
                ),

                const SizedBox(height: 20),

                const Text(
                  'Agrega una fotografía',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: oscuro,
                    fontSize: 21,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                const SizedBox(height: 8),

                const Text(
                  'Selecciona una imagen como evidencia '
                  'de tu actividad.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: gris, fontSize: 14, height: 1.5),
                ),

                const SizedBox(height: 18),

                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 7,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEEF2FF),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'Formatos permitidos: JPG y PNG',
                    style: TextStyle(
                      color: azul,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFA7F3D0)),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Column(
          children: [
            Container(
              width: double.infinity,
              height: 310,
              color: const Color(0xFFE2E8F0),
              child: Image.memory(
                imagen!,
                fit: BoxFit.contain,
                errorBuilder: (_, _, _) =>
                    const Center(child: Text('No se pudo mostrar la imagen')),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFD1FAE5),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.check_circle_rounded,
                      color: verde,
                      size: 26,
                    ),
                  ),

                  const SizedBox(width: 12),

                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          foto?.name ?? 'Imagen',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: oscuro,
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),

                        const SizedBox(height: 5),

                        Text(
                          '${tamanoArchivo()} · Imagen seleccionada',
                          style: const TextStyle(color: verde, fontSize: 12),
                        ),
                      ],
                    ),
                  ),

                  IconButton(
                    tooltip: 'Eliminar imagen',
                    onPressed: ocupado ? null : eliminarFoto,
                    icon: const Icon(Icons.delete_outline_rounded, color: rojo),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget botonSeleccion({
    required String titulo,
    required String descripcion,
    required IconData icono,
    required Color color,
    required Color colorFondo,
    required VoidCallback? accion,
  }) {
    return Material(
      color: colorFondo,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: accion,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: color.withValues(alpha: 0.15)),
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icono, color: Colors.white, size: 29),
              ),

              const SizedBox(height: 14),

              Text(
                titulo,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: color,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 6),

              Text(
                descripcion,
                textAlign: TextAlign.center,
                style: const TextStyle(color: gris, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget opcionesImagen() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final botones = [
          botonSeleccion(
            titulo: 'Tomar foto',
            descripcion: tieneCamara
                ? 'Usar la cámara del dispositivo'
                : 'Disponible en Android',
            icono: Icons.camera_alt_rounded,
            color: tieneCamara ? violeta : gris,
            colorFondo: tieneCamara
                ? const Color(0xFFF3E8FF)
                : const Color(0xFFF1F5F9),
            accion: ocupado || !tieneCamara ? null : () => elegir(true),
          ),

          botonSeleccion(
            titulo: foto == null ? 'Elegir imagen' : 'Cambiar imagen',
            descripcion: 'Seleccionar desde tus archivos',
            icono: Icons.photo_library_rounded,
            color: cian,
            colorFondo: const Color(0xFFECFEFF),
            accion: ocupado ? null : () => elegir(false),
          ),
        ];

        if (constraints.maxWidth < 420) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [botones[0], const SizedBox(height: 14), botones[1]],
          );
        }

        return Row(
          children: [
            Expanded(child: botones[0]),
            const SizedBox(width: 16),
            Expanded(child: botones[1]),
          ],
        );
      },
    );
  }

  Widget avisoInformacion() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF2FF),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFC7D2FE)),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline_rounded, color: azul, size: 23),

          SizedBox(width: 12),

          Expanded(
            child: Text(
              'La fotografía se guarda en tu dispositivo. '
              'SIGAF registra los datos del archivo como '
              'evidencia de la actividad.',
              style: TextStyle(
                color: Color(0xFF4338CA),
                fontSize: 13,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget botonEntrega() {
    final habilitado = foto != null && !ocupado;

    return Container(
      height: 56,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(15),
        gradient: habilitado
            ? const LinearGradient(colors: [azul, violeta])
            : null,
        color: habilitado ? null : const Color(0xFFE2E8F0),
      ),
      child: FilledButton(
        onPressed: habilitado ? confirmarEntrega : null,
        style: FilledButton.styleFrom(
          backgroundColor: Colors.transparent,
          disabledBackgroundColor: Colors.transparent,
          foregroundColor: Colors.white,
          disabledForegroundColor: gris,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
        ),
        child: enviando
            ? const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.5,
                      color: azul,
                    ),
                  ),

                  SizedBox(width: 12),

                  Text('Registrando entrega...'),
                ],
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.send_rounded),

                  SizedBox(width: 12),

                  Text(
                    'Confirmar entrega',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !ocupado,
      child: Scaffold(
        backgroundColor: fondo,
        appBar: AppBar(
          backgroundColor: Colors.white,
          surfaceTintColor: Colors.transparent,
          foregroundColor: oscuro,
          title: const Text(
            'Entregar actividad',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          actions: const [
            Padding(
              padding: EdgeInsets.only(right: 22),
              child: Icon(Icons.school_rounded, color: azul, size: 29),
            ),
          ],
        ),
        body: LayoutBuilder(
          builder: (context, constraints) {
            final padding = constraints.maxWidth > 700 ? 28.0 : 16.0;

            return SingleChildScrollView(
              padding: EdgeInsets.all(padding),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 950),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      encabezadoActividad(),

                      const SizedBox(height: 28),

                      tituloSeccion(
                        'Evidencia de la actividad',
                        'Adjunta una fotografía para registrar '
                            'la entrega de tu trabajo.',
                      ),

                      const SizedBox(height: 18),

                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(color: const Color(0xFFE2E8F0)),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x080F172A),
                              blurRadius: 20,
                              offset: Offset(0, 5),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            espacioImagen(),

                            const SizedBox(height: 20),

                            opcionesImagen(),

                            if (ocupado && !enviando) ...[
                              const SizedBox(height: 20),

                              const LinearProgressIndicator(color: azul),
                            ],
                          ],
                        ),
                      ),

                      const SizedBox(height: 22),

                      avisoInformacion(),

                      const SizedBox(height: 24),

                      botonEntrega(),

                      if (foto == null) ...[
                        const SizedBox(height: 10),

                        const Text(
                          'Selecciona una fotografía para continuar.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: gris, fontSize: 12),
                        ),
                      ],

                      const SizedBox(height: 30),

                      const Text(
                        'SIGAF · Universidad Autónoma de Aguascalientes',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Color(0xFF94A3B8),
                          fontSize: 12,
                        ),
                      ),

                      const SizedBox(height: 15),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
