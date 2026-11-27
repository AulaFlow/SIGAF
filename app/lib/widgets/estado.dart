import 'package:flutter/material.dart';

class MensajeError extends StatelessWidget {
  final String texto;
  final VoidCallback reintentar;
  const MensajeError({
    super.key,
    required this.texto,
    required this.reintentar,
  });
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 40),
          Text(texto, textAlign: TextAlign.center),
          TextButton(onPressed: reintentar, child: const Text('Reintentar')),
        ],
      ),
    ),
  );
}
