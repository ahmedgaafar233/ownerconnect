import 'package:flutter_dotenv/flutter_dotenv.dart';

/// The backend returns media paths (resort logos, etc.) as either an
/// already-absolute URL or a bare `/media/...` path, depending on whether
/// the view that built the serializer had request context. Normalizes both
/// into a URL the app can load directly.
String? resolveMediaUrl(String? path) {
  if (path == null || path.isEmpty) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  final base = dotenv.env['API_BASE_URL'] ?? '';
  if (base.isEmpty) return path;
  return '${base.endsWith('/') ? base.substring(0, base.length - 1) : base}$path';
}
