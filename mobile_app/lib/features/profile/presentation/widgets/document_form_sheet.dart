import 'package:flutter/material.dart';

import '../../../../core/utils/app_localizations.dart';
import '../../data/models/lease_inputs.dart';
import 'id_photo.dart';

/// The label of a paper's kind, for lists and the picker.
String documentKindLabelKey(String kind) => switch (kind) {
      'MARRIAGE_CERT' => 'doc_kind_marriage',
      'PASSPORT' => 'doc_kind_passport',
      _ => 'doc_kind_other',
    };

/// Collects one paper for the village (marriage certificate, passport, other).
/// Returns the [DocumentInput], or null if dismissed.
Future<DocumentInput?> showDocumentFormSheet(BuildContext context, {IdPhotoPicker pickPhoto = pickWithImagePicker}) {
  return showModalBottomSheet<DocumentInput>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _DocumentFormSheet(pickPhoto: pickPhoto),
  );
}

class _DocumentFormSheet extends StatefulWidget {
  const _DocumentFormSheet({required this.pickPhoto});

  final IdPhotoPicker pickPhoto;

  @override
  State<_DocumentFormSheet> createState() => _DocumentFormSheetState();
}

class _DocumentFormSheetState extends State<_DocumentFormSheet> {
  final _label = TextEditingController();
  String _kind = 'MARRIAGE_CERT';
  String? _photo;

  @override
  void dispose() {
    _label.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    const kinds = ['MARRIAGE_CERT', 'PASSPORT', 'OTHER'];

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(loc.translate('rent_add_document'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              children: [
                for (final kind in kinds)
                  ChoiceChip(
                    label: Text(loc.translate(documentKindLabelKey(kind))),
                    selected: _kind == kind,
                    onSelected: (_) => setState(() => _kind = kind),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _label,
              decoration: InputDecoration(labelText: loc.translate('doc_label_hint')),
            ),
            const SizedBox(height: 12),
            IdPhotoTile(
              label: loc.translate(documentKindLabelKey(_kind)),
              path: _photo,
              height: 120,
              onTap: () async {
                final path = await chooseAndPickPhoto(context, widget.pickPhoto);
                if (path != null && mounted) setState(() => _photo = path);
              },
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _photo == null
                  ? null
                  : () => Navigator.of(context).pop(
                        DocumentInput(kind: _kind, label: _label.text.trim(), photoPath: _photo!),
                      ),
              child: Text(loc.translate('save_button')),
            ),
          ],
        ),
      ),
    );
  }
}
