import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:path_provider/path_provider.dart';

import 'archivo_io.dart' if (dart.library.html) 'archivo_web.dart' as archivo;

class Camara {
  final picker = ImagePicker();
  Future<XFile?> elegir({bool camara = false}) async {
    if (camara && !kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      final p = await Permission.camera.request();
      if (p.isPermanentlyDenied) await openAppSettings();
      if (p.isGranted) {
        try {
          return await picker.pickImage(
            source: ImageSource.camera,
            maxWidth: 1600,
            imageQuality: 80,
          );
        } catch (_) {}
      }
    }
    return picker.pickImage(source: ImageSource.gallery);
  }

  Future<Map<String, dynamic>> guardar(String id, XFile foto) async {
    final bytes = await foto.readAsBytes();
    final png =
        bytes.length > 4 &&
        bytes[0] == 137 &&
        bytes[1] == 80 &&
        bytes[2] == 78 &&
        bytes[3] == 71;
    final jpg = bytes.length > 2 && bytes[0] == 255 && bytes[1] == 216;
    if (!png && !jpg) throw Exception('Selecciona una imagen JPG o PNG');
    final ruta =
        'entregas/$id/foto_${DateTime.now().millisecondsSinceEpoch}.${png ? 'png' : 'jpg'}';
    if (kIsWeb) {
      await (await SharedPreferences.getInstance()).setString(
        'sigaf_foto_$ruta',
        base64Encode(bytes),
      );
    } else {
      final dir = await getApplicationDocumentsDirectory();
      await archivo.guardar('${dir.path}/$ruta', bytes);
    }
    return {
      'archivo_ruta': ruta,
      'archivo_tamano_bytes': bytes.length,
      'archivo_tipo': png ? 'image/png' : 'image/jpeg',
    };
  }
}
