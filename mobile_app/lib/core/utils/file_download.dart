import 'dart:io';
import 'dart:typed_data';

import 'package:file_saver/file_saver.dart';
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

/// Lets the owner pick where to keep a PDF (the system "save as" dialog —
/// Downloads, Drive, ...). Returns whether it was saved; false if they
/// backed out of the dialog.
Future<bool> savePdfToDevice(List<int> bytes, String nameWithoutExtension) async {
  final path = await FileSaver.instance.saveAs(
    name: nameWithoutExtension,
    bytes: Uint8List.fromList(bytes),
    ext: 'pdf',
    mimeType: MimeType.pdf,
  );
  return path != null && path.isNotEmpty;
}
