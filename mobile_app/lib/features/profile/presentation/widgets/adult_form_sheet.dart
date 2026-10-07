import 'package:flutter/material.dart';

import '../../../../core/utils/app_localizations.dart';
import '../../data/models/lease_inputs.dart';
import 'id_photo.dart';

/// Collects one adult staying in the unit (name, ID number, relation, ID photo).
/// Returns the [AdultInput], or null if dismissed.
Future<AdultInput?> showAdultFormSheet(BuildContext context, {IdPhotoPicker pickPhoto = pickWithImagePicker}) {
  return showModalBottomSheet<AdultInput>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _AdultFormSheet(pickPhoto: pickPhoto),
  );
}

class _AdultFormSheet extends StatefulWidget {
  const _AdultFormSheet({required this.pickPhoto});

  final IdPhotoPicker pickPhoto;

  @override
  State<_AdultFormSheet> createState() => _AdultFormSheetState();
}

class _AdultFormSheetState extends State<_AdultFormSheet> {
  final _name = TextEditingController();
  final _idNumber = TextEditingController();
  String _relation = 'SPOUSE';
  String? _photo;

  @override
  void initState() {
    super.initState();
    _name.addListener(() => setState(() {}));
    _idNumber.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _name.dispose();
    _idNumber.dispose();
    super.dispose();
  }

  bool get _valid => _name.text.trim().isNotEmpty && _idNumber.text.trim().isNotEmpty && _photo != null;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    const relations = [
      ('SPOUSE', 'adult_relation_spouse'),
      ('FAMILY', 'adult_relation_family'),
      ('OTHER', 'adult_relation_other'),
    ];

    return Padding(
      // Lifts the form above the keyboard.
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(loc.translate('adult_form_title'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            TextField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(labelText: loc.translate('adult_name')),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _idNumber,
              decoration: InputDecoration(labelText: loc.translate('adult_id_number')),
            ),
            const SizedBox(height: 12),
            Text(loc.translate('adult_relation_label'), style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final (value, key) in relations)
                  ChoiceChip(
                    label: Text(loc.translate(key)),
                    selected: _relation == value,
                    onSelected: (_) => setState(() => _relation = value),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            IdPhotoTile(
              label: loc.translate('adult_id_photo'),
              path: _photo,
              height: 120,
              onTap: () async {
                final path = await chooseAndPickPhoto(context, widget.pickPhoto);
                if (path != null && mounted) setState(() => _photo = path);
              },
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _valid
                  ? () => Navigator.of(context).pop(AdultInput(
                        fullName: _name.text.trim(),
                        nationalId: _idNumber.text.trim(),
                        relation: _relation,
                        photoPath: _photo!,
                      ))
                  : null,
              child: Text(loc.translate('save_button')),
            ),
          ],
        ),
      ),
    );
  }
}
