import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../servicios/sesion.dart';

class LoginPantalla extends StatefulWidget {
  const LoginPantalla({super.key});

  @override
  State<LoginPantalla> createState() => _LoginState();
}

class _LoginState extends State<LoginPantalla> {
  final form = GlobalKey<FormState>();
  final correo = TextEditingController();
  final clave = TextEditingController();

  bool cargando = false;
  bool ocultar = true;

  static const azul = Color(0xFF4F46E5);
  static const oscuro = Color(0xFF0F172A);
  static const violeta = Color(0xFF9333EA);
  static const cian = Color(0xFF06B6D4);

  @override
  void dispose() {
    correo.dispose();
    clave.dispose();
    super.dispose();
  }

  Future<void> enviar() async {
    if (cargando || !form.currentState!.validate()) {
      return;
    }

    setState(() => cargando = true);

    try {
      await context.read<Sesion>().login(correo.text.trim(), clave.text);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('$e'),
            backgroundColor: const Color(0xFFDC2626),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => cargando = false);
      }
    }
  }

  Widget circulo(double size, Color color) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: 0.12),
      ),
    );
  }

  Widget beneficio(IconData icono, String texto, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icono, color: color),
          ),
          const SizedBox(width: 15),
          Expanded(
            child: Text(
              texto,
              style: const TextStyle(color: Colors.white, fontSize: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget bienvenida() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0F172A), Color(0xFF312E81), Color(0xFF6D28D9)],
        ),
      ),
      child: Stack(
        children: [
          Positioned(top: -50, right: -60, child: circulo(260, Colors.white)),

          Positioned(bottom: -60, left: -70, child: circulo(300, cian)),

          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 45, vertical: 30),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(24),
                      gradient: const LinearGradient(colors: [azul, violeta]),
                    ),
                    child: const Icon(
                      Icons.school_rounded,
                      color: Colors.white,
                      size: 48,
                    ),
                  ),

                  const SizedBox(height: 25),

                  const Text(
                    'SIGAF',
                    style: TextStyle(
                      fontSize: 54,
                      fontWeight: FontWeight.w900,
                      color: Colors.white,
                      letterSpacing: 3,
                    ),
                  ),

                  const SizedBox(height: 12),

                  const Text(
                    'Tu vida académica,\nen un solo lugar.',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 32,
                      height: 1.2,
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  const SizedBox(height: 20),

                  const Text(
                    'Sistema Integral de Gestión Académica. '
                    'Consulta tus calificaciones, administra '
                    'tus actividades y mantente conectado.',
                    style: TextStyle(
                      color: Color(0xFFCBD5E1),
                      fontSize: 16,
                      height: 1.7,
                    ),
                  ),

                  const SizedBox(height: 28),

                  beneficio(
                    Icons.bar_chart_rounded,
                    'Consulta tus calificaciones',
                    const Color(0xFF67E8F9),
                  ),

                  beneficio(
                    Icons.assignment_rounded,
                    'Organiza tus actividades',
                    const Color(0xFFC4B5FD),
                  ),

                  beneficio(
                    Icons.cloud_done_rounded,
                    'Accede a tu información académica',
                    const Color(0xFF6EE7B7),
                  ),

                  const SizedBox(height: 12),

                  const Text(
                    'AulaFlow · Universidad Autónoma de Aguascalientes',
                    style: TextStyle(
                      color: Color(0xFFCBD5E1),
                      fontSize: 12,
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  InputDecoration decoracion(
    String titulo,
    String ejemplo,
    IconData icono, {
    Widget? suffix,
  }) {
    return InputDecoration(
      labelText: titulo,
      hintText: ejemplo,
      prefixIcon: Icon(icono, color: azul),
      suffixIcon: suffix,
      filled: true,
      fillColor: const Color(0xFFF8FAFC),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 20),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: const BorderSide(color: azul, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: const BorderSide(color: Color(0xFFDC2626)),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(15),
        borderSide: const BorderSide(color: Color(0xFFDC2626), width: 2),
      ),
      errorMaxLines: 2,
    );
  }

  Widget formulario(bool movil) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Container(
            padding: const EdgeInsets.all(28),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: oscuro.withValues(alpha: 0.08),
                  blurRadius: 40,
                  offset: const Offset(0, 15),
                ),
              ],
            ),
            child: Form(
              key: form,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      padding: const EdgeInsets.all(15),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [azul, violeta]),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Icon(
                        Icons.school_rounded,
                        size: 38,
                        color: Colors.white,
                      ),
                    ),
                  ),

                  if (movil) ...[
                    const SizedBox(height: 12),
                    const Text(
                      'SIGAF',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        color: oscuro,
                      ),
                    ),
                  ],

                  const SizedBox(height: 20),

                  const Text(
                    '¡Bienvenido!',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.bold,
                      color: oscuro,
                    ),
                  ),

                  const SizedBox(height: 8),

                  const Text(
                    'Inicia sesión en tu portal académico',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0xFF64748B), fontSize: 14),
                  ),

                  const SizedBox(height: 25),

                  // Campo de correo electrónico.
                  TextFormField(
                    controller: correo,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: decoracion(
                      'Correo electrónico',
                      'alumno@sigaf.test',
                      Icons.email_outlined,
                    ),
                    validator: (v) {
                      if (v == null ||
                          !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                              .hasMatch(v.trim())) {
                        return 'Ingresa un correo válido';
                      }

                      return null;
                    },
                  ),

                  const SizedBox(height: 18),

                  // Campo de contraseña.
                  TextFormField(
                    controller: clave,
                    obscureText: ocultar,
                    textInputAction: TextInputAction.done,
                    onFieldSubmitted: (_) => enviar(),
                    decoration: decoracion(
                      'Contraseña',
                      'Escribe tu contraseña',
                      Icons.lock_outline_rounded,
                      suffix: IconButton(
                        tooltip: ocultar
                            ? 'Mostrar contraseña'
                            : 'Ocultar contraseña',
                        onPressed: () {
                          setState(() => ocultar = !ocultar);
                        },
                        icon: Icon(
                          ocultar
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                          color: Colors.blueGrey,
                        ),
                      ),
                    ),
                    validator: (v) {
                      if (v == null || v.isEmpty) {
                        return 'Ingresa tu contraseña';
                      }

                      return null;
                    },
                  ),

                  const SizedBox(height: 25),

                  // Botón de inicio de sesión.
                  Container(
                    height: 54,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [azul, violeta]),
                      borderRadius: BorderRadius.circular(15),
                      boxShadow: [
                        BoxShadow(
                          color: azul.withValues(alpha: 0.25),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: FilledButton(
                      onPressed: cargando ? null : enviar,
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        disabledBackgroundColor: Colors.transparent,
                        shadowColor: Colors.transparent,
                        foregroundColor: Colors.white,
                        disabledForegroundColor: Colors.white70,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(15),
                        ),
                      ),
                      child: cargando
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Flexible(
                                  child: Text(
                                    'Iniciar sesión',
                                    textAlign: TextAlign.center,
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 16,
                                    ),
                                  ),
                                ),

                                SizedBox(width: 10),

                                Icon(Icons.arrow_forward_rounded),
                              ],
                            ),
                    ),
                  ),

                  const SizedBox(height: 22),

                  // Texto institucional adaptable.
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.shield_outlined,
                        size: 16,
                        color: Color(0xFF10B981),
                      ),

                      SizedBox(width: 6),

                      Flexible(
                        child: Text(
                          'Portal académico institucional',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF64748B),
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 20),

                  const Divider(color: Color(0xFFE2E8F0)),

                  const SizedBox(height: 10),

                  const Text(
                    '© 2026 AulaFlow · SIGAF',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final movil = constraints.maxWidth < 900;

          return Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFFE0E7FF),
                  Color(0xFFF5F3FF),
                  Color(0xFFCFFAFE),
                ],
              ),
            ),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: const Duration(milliseconds: 650),
              builder: (context, value, child) {
                return Opacity(
                  opacity: value,
                  child: Transform.translate(
                    offset: Offset(0, 15 * (1 - value)),
                    child: child,
                  ),
                );
              },
              child: movil
                  ? SafeArea(child: formulario(true))
                  : Row(
                      children: [
                        Expanded(flex: 5, child: bienvenida()),
                        Expanded(flex: 5, child: formulario(false)),
                      ],
                    ),
            ),
          );
        },
      ),
    );
  }
}
