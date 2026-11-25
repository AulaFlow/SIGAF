import 'package:sqflite/sqflite.dart' as sq;

sq.DatabaseFactory factoryLocal() =>
    throw UnsupportedError('SQLite no disponible en web');
