import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';
import 'api_cliente.dart';
import 'almacen_local.dart';

class Sesion extends ChangeNotifier {
  final ApiCliente api;
  final AlmacenLocal local;
  final storage = const FlutterSecureStorage();
  bool lista = false;
  bool activa = false;
  Sesion(this.api, this.local) {
    api.onUnauthorized = salir;
  }
  Future<void> restaurar() async {
    try {
      if (!demo) {
        api.token = await storage.read(key: 'sigaf_token');
        activa = api.token != null;
      }
    } finally {
      lista = true;
      notifyListeners();
    }
  }

  Future<void> login(String correo, String clave) async {
    await local.limpiar();
    if (!demo) {
      final r = await api.request('POST', '/auth/login', {
        'correo': correo,
        'contrasena': clave,
      });
      final token = r['access_token'] as String;
      await storage.write(key: 'sigaf_token', value: token);
      api.token = token;
    }
    activa = true;
    notifyListeners();
  }

  Future<void> salir() async {
    api.token = null;
    activa = false;
    notifyListeners();
    await storage.delete(key: 'sigaf_token');
    await local.limpiar();
  }
}
