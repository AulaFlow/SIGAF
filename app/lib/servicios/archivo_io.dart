import 'dart:io';

Future<void> guardar(String ruta, List<int> bytes) async {
  final f = File(ruta);
  await f.parent.create(recursive: true);
  await f.writeAsBytes(bytes);
}
