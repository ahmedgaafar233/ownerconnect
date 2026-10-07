import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';

/// Picks a photo and returns its path (null if cancelled). Injectable so tests
/// don't need a real camera or gallery.
typedef IdPhotoPicker = Future<String?> Function(ImageSource source);

Future<String?> pickWithImagePicker(ImageSource source) async {
  // Shrunk on the phone: an 8 MB upload limit shouldn't be hit by a 12 MP photo.
  final file = await ImagePicker().pickImage(source: source, maxWidth: 1800, imageQuality: 85);
  return file?.path;
}

/// Asks camera or gallery, then picks. Null when the person backs out.
Future<String?> chooseAndPickPhoto(BuildContext context, IdPhotoPicker pick) async {
  final loc = AppLocalizations.of(context);
  final source = await showModalBottomSheet<ImageSource>(
    context: context,
    builder: (sheetContext) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.photo_camera_outlined),
            title: Text(loc.translate('rent_id_photo_camera')),
            onTap: () => Navigator.of(sheetContext).pop(ImageSource.camera),
          ),
          ListTile(
            leading: const Icon(Icons.photo_library_outlined),
            title: Text(loc.translate('rent_id_photo_gallery')),
            onTap: () => Navigator.of(sheetContext).pop(ImageSource.gallery),
          ),
        ],
      ),
    ),
  );
  if (source == null) return null;
  return pick(source);
}

/// A tappable photo slot: the empty prompt, or the chosen picture with a "change" badge.
class IdPhotoTile extends StatelessWidget {
  const IdPhotoTile({
    Key? key,
    required this.label,
    required this.path,
    required this.onTap,
    this.height = 150,
  }) : super(key: key);

  final String label;
  final String? path;
  final VoidCallback onTap;
  final double height;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        height: height,
        width: double.infinity,
        decoration: BoxDecoration(
          color: AppColors.glassFill,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: path == null
            ? Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.badge_outlined, size: 36, color: AppColors.primary),
                  const SizedBox(height: 8),
                  Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text(loc.translate('rent_id_photo_add'), style: const TextStyle(color: AppColors.primary)),
                ],
              )
            : Stack(
                fit: StackFit.expand,
                children: [
                  Image.file(
                    File(path!),
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const Center(child: Icon(Icons.broken_image_outlined, size: 36)),
                  ),
                  PositionedDirectional(
                    bottom: 8,
                    end: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(20)),
                      child: Text(
                        loc.translate('rent_id_photo_change'),
                        style: const TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
