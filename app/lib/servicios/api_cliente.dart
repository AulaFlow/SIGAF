import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';

class ApiError implements Exception {
  final int status;
  final String mensaje;
  ApiError(this.status, this.mensaje);
  @override
  String toString() => mensaje;
}

class ApiCliente {
  String? token;
  Future<void> Function()? onUnauthorized;
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final uri = Uri.parse('$apiUrl$path');
    http.Response r;
    try {
      r =
          await (method == 'GET'
                  ? http.get(uri, headers: headers)
                  : http.post(uri, headers: headers, body: jsonEncode(body)))
              .timeout(const Duration(seconds: 10));
    } on TimeoutException {
      throw ApiError(0, 'Sin conexión: tiempo agotado');
    } on http.ClientException {
      throw ApiError(0, 'Sin conexión');
    }
    dynamic data;
    try {
      data = jsonDecode(r.body);
    } catch (_) {
      data = null;
    }
    if (r.statusCode >= 200 && r.statusCode < 300) return data;
    if (r.statusCode == 401 && token != null) await onUnauthorized?.call();
    throw ApiError(
      r.statusCode,
      r.statusCode == 503
          ? 'Servicio no disponible'
          : r.statusCode == 403
          ? 'No tienes permiso'
          : data is Map && data['mensaje'] != null
          ? data['mensaje'].toString()
          : 'Error HTTP ${r.statusCode}',
    );
  }
}
