import 'dart:io';

import 'package:sqflite/sqflite.dart' as sq;
import 'package:sqflite_common_ffi/sqflite_ffi.dart' as ffi;

sq.DatabaseFactory factoryLocal() {
  if (Platform.isWindows) {
    ffi.sqfliteFfiInit();
    return ffi.databaseFactoryFfi;
  }
  return sq.databaseFactory;
}
