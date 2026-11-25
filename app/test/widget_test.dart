import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:sigaf/pantallas/login_pantalla.dart';
import 'package:sigaf/pantallas/lista_pantalla.dart';
import 'package:sigaf/repositorios/alumno_repositorio.dart';
import 'package:sigaf/repositorios/alumno_repo_falso.dart';
import 'package:sigaf/widgets/estado.dart';

void main() {
  // PRUEBA 1: Validaciones del inicio de sesión.
  testWidgets('Login valida campos', (t) async {
    await t.pumpWidget(const MaterialApp(home: LoginPantalla()));

    // Esperar a que termine la animación del login.
    await t.pumpAndSettle();

    final boton = find.widgetWithText(FilledButton, 'Iniciar sesión');

    expect(boton, findsOneWidget);

    // Asegurar que el botón sea visible.
    await t.ensureVisible(boton);
    await t.pumpAndSettle();

    // Intentar iniciar sesión con los campos vacíos.
    await t.tap(boton);
    await t.pumpAndSettle();

    // Comprobar los mensajes de validación.
    expect(find.text('Ingresa un correo válido'), findsOneWidget);

    expect(find.text('Ingresa tu contraseña'), findsOneWidget);
  });

  // PRUEBA 2: Visualización de calificaciones.
  testWidgets('Boleta muestra materias', (t) async {
    await t.pumpWidget(
      Provider<AlumnoRepositorio>(
        create: (_) => AlumnoRepoFalso(),
        child: const MaterialApp(
          home: Scaffold(body: ListaPantalla(boleta: true)),
        ),
      ),
    );

    await t.pumpAndSettle();

    expect(find.text('Programación móvil'), findsOneWidget);

    expect(find.text('Bases de datos distribuidas'), findsOneWidget);

    expect(find.text('PROMEDIO GENERAL'), findsOneWidget);
  });

  // PRUEBA 3: Manejo de errores y reintento.
  testWidgets('Error ofrece reintentar', (t) async {
    bool llamado = false;

    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MensajeError(
            texto: 'Sin conexión',
            reintentar: () => llamado = true,
          ),
        ),
      ),
    );

    await t.pumpAndSettle();

    expect(find.text('Sin conexión'), findsOneWidget);

    expect(find.text('Reintentar'), findsOneWidget);

    await t.tap(find.text('Reintentar'));
    await t.pumpAndSettle();

    expect(llamado, isTrue);
  });
}
