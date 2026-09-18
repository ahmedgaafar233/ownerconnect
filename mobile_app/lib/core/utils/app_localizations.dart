import 'package:flutter/material.dart';

class AppLocalizations {
  final Locale locale;

  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations) ??
        AppLocalizations(const Locale('en'));
  }

  static const _localizedValues = <String, Map<String, String>>{
    'en': {
      'app_title': 'OwnerConnect',
      'charges_title': 'Unit Charges & Fees',
      'tickets_title': 'Support & Maintenance',
      'passes_title': 'Gate & Beach Passes',
      'pay_now': 'Pay Selected Charges',
      'create_ticket': 'New Support Request',
      'create_pass': 'New Visitor Pass',
      'no_charges': 'No charges found',
      'no_tickets': 'No support tickets found',
      'no_passes': 'No gate passes found',
      'status_published': 'Published',
      'status_paid': 'Paid',
      'status_unpaid': 'Unpaid',
      'unit': 'Unit',
      'amount': 'Amount',
      'remaining': 'Remaining',
      'details': 'Details',
      'qr_code': 'Show Entry QR Code',
      'login_title': 'Welcome to OwnerConnect',
      'login_subtitle': 'Select your country and enter your phone number to continue',
      'phone_hint': 'Phone number',
      'continue_button': 'Continue',
      'invalid_phone': 'Please enter a valid phone number',
      'dev_bypass_button': 'Developer Test Sign-In',
      'otp_title': 'Verification Code',
      'otp_subtitle': 'Enter the 6-digit code sent to',
      'verify_button': 'Verify',
      'resend_code': 'Resend Code',
      'resend_in': 'Resend code in',
      'pending_resort_title': 'Account Not Linked Yet',
      'pending_resort_message':
          'Your account exists but isn\'t linked to a resort/village yet. Please contact your resort administration.',
      'logout': 'Logout',
    },
    'ar': {
      'app_title': 'أونر كونكت',
      'charges_title': 'مستحقات وفواتير الوحدة',
      'tickets_title': 'الدعم الفني والصيانة',
      'passes_title': 'تصاريح البوابة والشاطئ',
      'pay_now': 'سداد المستحقات المحددة',
      'create_ticket': 'طلب صيانة جديد',
      'create_pass': 'تصريح دخول جديد',
      'no_charges': 'لا توجد مستحقات حالياً',
      'no_tickets': 'لا توجد تذاكر دعم فني',
      'no_passes': 'لا توجد تصاريح دخول',
      'status_published': 'معتمدة',
      'status_paid': 'مسددة',
      'status_unpaid': 'غير مسددة',
      'unit': 'الوحدة',
      'amount': 'المبلغ',
      'remaining': 'المتبقي',
      'details': 'التفاصيل',
      'qr_code': 'عرض رمز QR للدخول',
      'login_title': 'مرحباً بك في أونر كونكت',
      'login_subtitle': 'اختر دولتك وادخل رقم موبايلك للمتابعة',
      'phone_hint': 'رقم الموبايل',
      'continue_button': 'متابعة',
      'invalid_phone': 'من فضلك ادخل رقم موبايل صحيح',
      'dev_bypass_button': 'دخول تجريبي للمطورين',
      'otp_title': 'كود التفعيل',
      'otp_subtitle': 'ادخل الكود المكوّن من 6 أرقام المرسل إلى',
      'verify_button': 'تأكيد',
      'resend_code': 'إعادة إرسال الكود',
      'resend_in': 'إعادة الإرسال خلال',
      'pending_resort_title': 'الحساب لسه مش مربوط بقرية',
      'pending_resort_message':
          'حسابك موجود بس لسه محدش ربطه بقرية أو وحدة. من فضلك تواصل مع إدارة القرية.',
      'logout': 'تسجيل الخروج',
    },
  };

  String translate(String key) {
    return _localizedValues[locale.languageCode]?[key] ?? key;
  }
}

class AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) => ['en', 'ar'].contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async {
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(AppLocalizationsDelegate old) => false;
}
