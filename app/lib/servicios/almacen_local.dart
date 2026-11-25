import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart' as sq;

import 'factory_web.dart' if (dart.library.io) 'factory_io.dart' as plataforma;

class AlmacenLocal {
  sq.Database? _db;
  Future<sq.Database> db() async {
    if (_db != null) return _db!;
    final factory = plataforma.factoryLocal();
    final path = '${await factory.getDatabasesPath()}/sigaf_cache.db';
    return _db = await factory.openDatabase(
      path,
      options: sq.OpenDatabaseOptions(
        version: 1,
        onCreate: (d, v) async {
          await d.execute(
            'CREATE TABLE cache (grupo TEXT, id TEXT, datos TEXT, PRIMARY KEY(grupo,id))',
          );
          await d.execute(
            'CREATE TABLE fechas (grupo TEXT PRIMARY KEY, fecha TEXT)',
          );
        },
      ),
    );
  }

  Future<void> guardar(
    String grupo,
    List<Map<String, dynamic>> items,
    String llave,
  ) async {
    final fecha = DateTime.now().toIso8601String();
    if (kIsWeb) {
      final p = await SharedPreferences.getInstance();
      await p.setString(
        'sigaf_$grupo',
        jsonEncode({'items': items, 'fecha': fecha}),
      );
      return;
    }
    final d = await db();
    await d.transaction((t) async {
      await t.delete('cache', where: 'grupo = ?', whereArgs: [grupo]);
      for (final item in items) {
        await t.insert('cache', {
          'grupo': grupo,
          'id': item[llave].toString(),
          'datos': jsonEncode(item),
        }, conflictAlgorithm: sq.ConflictAlgorithm.replace);
      }
      await t.insert('fechas', {
        'grupo': grupo,
        'fecha': fecha,
      }, conflictAlgorithm: sq.ConflictAlgorithm.replace);
    });
  }

  Future<Map<String, dynamic>?> leer(String grupo) async {
    if (kIsWeb) {
      final s = (await SharedPreferences.getInstance()).getString(
        'sigaf_$grupo',
      );
      return s == null ? null : Map<String, dynamic>.from(jsonDecode(s));
    }
    final d = await db();
    final f = await d.query('fechas', where: 'grupo = ?', whereArgs: [grupo]);
    if (f.isEmpty) return null;
    final rows = await d.query('cache', where: 'grupo = ?', whereArgs: [grupo]);
    return {
      'items': rows.map((r) => jsonDecode(r['datos'] as String)).toList(),
      'fecha': f.first['fecha'],
    };
  }

  Future<void> limpiar() async {
    if (kIsWeb) {
      final p = await SharedPreferences.getInstance();
      for (final k in p.getKeys().where((k) => k.startsWith('sigaf_'))) {
        await p.remove(k);
      }
    } else {
      final d = await db();
      await d.delete('cache');
      await d.delete('fechas');
    }
  }
}
