import 'package:intl_phone_field/phone_number.dart';

/// [PhoneNumber.completeNumber] just concatenates the country dial code with
/// whatever digits were typed. Egyptians naturally type their local mobile
/// number with its leading 0 (e.g. 01222222222), which then becomes
/// "+2001222222222" instead of "+201222222222" — silently mismatching
/// whatever E.164 number staff stored for the owner. Strip that leading
/// zero before combining, the way local dialing conventions expect.
String normalizedCompleteNumber(PhoneNumber phone) {
  // phone.countryCode is already "+20"-style (the widget prepends the '+'),
  // so it's concatenated directly — do not add another '+' here.
  final number = phone.number.replaceFirst(RegExp(r'^0+'), '');
  return '${phone.countryCode}$number';
}
