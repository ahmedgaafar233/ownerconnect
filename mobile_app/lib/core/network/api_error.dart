import 'package:dio/dio.dart';

/// First human-readable message from a DRF error body — `{"field": ["msg"]}`,
/// `{"detail": "msg"}` or a bare list — falling back to the exception text
/// for anything else (network errors, non-JSON bodies).
String apiErrorMessage(Object error) {
  if (error is DioException) {
    final message = _firstMessage(error.response?.data);
    if (message != null) return message;
  }
  return error.toString();
}

String? _firstMessage(dynamic data) {
  // A long string is an HTML error page, not something to show a resident.
  if (data is String) return data.isNotEmpty && data.length < 300 ? data : null;
  final values = data is Map ? data.values : (data is List ? data : const []);
  for (final value in values) {
    final message = _firstMessage(value);
    if (message != null) return message;
  }
  return null;
}
