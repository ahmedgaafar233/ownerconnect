import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../core/theme/app_colors.dart';

/// A 6-box OTP input. Internally this is a single hidden [TextField] that
/// owns focus and receives every keystroke, with the boxes below just
/// rendering its current text — auto-advance and backspace-to-previous are
/// then "free" (there's only ever one field, so there's nothing to hand
/// focus between). An earlier version used one TextField per box wired
/// together with FocusNodes; on real devices that pattern needed a manual
/// tap per box and never auto-advanced reliably (Android keyboards don't
/// consistently re-raise focus requests fired from inside onChanged).
class OtpBoxField extends StatefulWidget {
  final int length;
  final ValueChanged<String> onCompleted;

  const OtpBoxField({Key? key, this.length = 6, required this.onCompleted})
      : super(key: key);

  @override
  State<OtpBoxField> createState() => _OtpBoxFieldState();
}

class _OtpBoxFieldState extends State<OtpBoxField> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _focusNode = FocusNode();
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    setState(() {});
    if (value.length == widget.length) {
      _focusNode.unfocus();
      widget.onCompleted(value);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Force LTR regardless of the app's locale: this is a numeric code, not
    // language-direction text, and in an RTL (Arabic) context the ambient
    // Directionality would otherwise lay the boxes out right-to-left,
    // putting the first digit typed in the rightmost box.
    return Directionality(
      textDirection: TextDirection.ltr,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => _focusNode.requestFocus(),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: List.generate(widget.length, (index) {
                final filled = index < _controller.text.length;
                final isActive =
                    index == _controller.text.length && _focusNode.hasFocus;
                return Container(
                  width: 46,
                  height: 56,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: isActive
                          ? AppColors.primary
                          : AppColors.textSecondary.withOpacity(0.4),
                      width: isActive ? 2 : 1,
                    ),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    filled ? _controller.text[index] : '',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary),
                  ),
                );
              }),
            ),
            // The real input, invisible and stretched over the boxes so any
            // tap on the row focuses it and opens the number keyboard.
            Opacity(
              opacity: 0,
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                autofocus: true,
                keyboardType: TextInputType.number,
                maxLength: widget.length,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(
                    counterText: '', border: InputBorder.none),
                onChanged: _onChanged,
                showCursor: false,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
