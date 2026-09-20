import 'dart:io';

import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

/// Writes already-downloaded bytes to a temp file and opens it with
/// whatever the device has registered for that file type (a PDF viewer,
/// for a receipt/clearance statement). Returns whether the open succeeded.
Future<bool> saveAndOpenFile(List<int> bytes, String filename) async {
  final dir = await getTemporaryDirectory();
  final file = File('${dir.path}/$filename');
  await file.writeAsBytes(bytes, flush: true);
  final result = await OpenFilex.open(file.path);
  return result.type == ResultType.done;
}
