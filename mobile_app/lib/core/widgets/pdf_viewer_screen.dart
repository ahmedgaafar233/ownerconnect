import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../theme/app_colors.dart';
import '../utils/app_localizations.dart';
import '../utils/file_download.dart';
import 'app_loading_indicator.dart';

/// Shows a PDF (a payment receipt or a clearance statement) inside the app,
/// so the owner can read it without downloading anything first — with a
/// button to keep a copy and one to hand it to another app. The bytes are
/// fetched through [loadBytes] (the authenticated Dio client), so the screen
/// opens at once and shows a spinner while the file comes down.
class PdfViewerScreen extends StatefulWidget {
  const PdfViewerScreen({
    Key? key,
    required this.loadBytes,
    required this.title,
    required this.fileName,
  }) : super(key: key);

  final Future<List<int>> Function() loadBytes;
  final String title;

  /// Without the .pdf extension.
  final String fileName;

  @override
  State<PdfViewerScreen> createState() => _PdfViewerScreenState();
}

class _PdfViewerScreenState extends State<PdfViewerScreen> {
  PdfControllerPinch? _controller;
  List<int>? _bytes;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _hasError = false;
      _bytes = null;
    });
    try {
      final bytes = await widget.loadBytes();
      if (!mounted) return;
      _controller?.dispose();
      setState(() {
        _bytes = bytes;
        _controller = PdfControllerPinch(document: PdfDocument.openData(Uint8List.fromList(bytes)));
      });
    } catch (_) {
      if (mounted) setState(() => _hasError = true);
    }
  }

  Future<void> _download() async {
    final loc = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final saved = await savePdfToDevice(_bytes!, widget.fileName);
      if (saved) messenger.showSnackBar(SnackBar(content: Text(loc.translate('file_saved'))));
    } catch (_) {
      messenger.showSnackBar(
        SnackBar(content: Text(loc.translate('pdf_load_error')), backgroundColor: AppColors.error),
      );
    }
  }

  Future<void> _openElsewhere() async {
    final loc = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final opened = await saveAndOpenFile(_bytes!, '${widget.fileName}.pdf');
    if (!opened) {
      messenger.showSnackBar(
        SnackBar(content: Text(loc.translate('pdf_load_error')), backgroundColor: AppColors.error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final ready = _bytes != null && _controller != null;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.download_rounded),
            tooltip: loc.translate('pdf_download'),
            onPressed: ready ? _download : null,
          ),
          IconButton(
            icon: const Icon(Icons.open_in_new_rounded),
            tooltip: loc.translate('pdf_open_external'),
            onPressed: ready ? _openElsewhere : null,
          ),
        ],
      ),
      body: _hasError
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      loc.translate('pdf_load_error'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton(onPressed: _load, child: Text(loc.translate('retry_button'))),
                  ],
                ),
              ),
            )
          : !ready
              ? const Center(child: AppLoadingIndicator())
              : Stack(
                  children: [
                    PdfViewPinch(
                      controller: _controller!,
                      backgroundDecoration: const BoxDecoration(color: AppColors.backgroundElevated),
                      onDocumentError: (_) => setState(() => _hasError = true),
                    ),
                    Positioned(
                      bottom: 16,
                      left: 0,
                      right: 0,
                      child: Center(
                        child: PdfPageNumber(
                          controller: _controller!,
                          builder: (context, loadingState, page, pagesCount) {
                            if ((pagesCount ?? 0) < 2) return const SizedBox.shrink();
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                              decoration: BoxDecoration(
                                color: Colors.black.withOpacity(0.55),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                '$page / $pagesCount',
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
