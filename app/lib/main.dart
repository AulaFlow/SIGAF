import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'config.dart';
import 'servicios/api_cliente.dart';
import 'servicios/almacen_local.dart';
import 'servicios/sesion.dart';
import 'repositorios/alumno_repositorio.dart';
import 'repositorios/alumno_repo_api.dart';
import 'repositorios/alumno_repo_falso.dart';
import 'pantallas/login_pantalla.dart';
import 'pantallas/inicio_pantalla.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ApiCliente();
  final local = AlmacenLocal();
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => Sesion(api, local)..restaurar()),
        Provider<AlumnoRepositorio>(
          create: (_) => demo ? AlumnoRepoFalso() : AlumnoRepoApi(api, local),
        ),
      ],
      child: const SigafApp(),
    ),
  );
}

class SigafApp extends StatelessWidget {
  const SigafApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'SIGAF',
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff173c68)),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      scaffoldBackgroundColor: const Color(0xfff4f6fa),
    ),
    home: Consumer<Sesion>(
      builder: (_, s, _) => !s.lista
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : s.activa
          ? const InicioPantalla()
          : const LoginPantalla(),
    ),
  );
}
