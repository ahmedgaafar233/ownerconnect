# OwnerConnect — mobile app

The Flutter app for property owners and tenants of a resort village. It talks to the Django backend in the repository root; see the [main README](../README.md) for what the whole system does and for screenshots.

## What is in it

- Sign-in with phone OTP, Google or e-mail (Firebase), exchanged for the backend's own JWT. The village is chosen once, then locked to the signed-in account.
- Charges across all of an owner's units: combined total, month filter, online payment, deferral, partial payment, pay at the accounts office, payment history and PDF receipts.
- Profile with every unit, and **renting a unit out** (short or long term): tenant details and ID photo, adults, papers for Security, extend / renew / end, meter readings, a QR code per adult.
- For tenants: a "Your stay" card with dates, entry meter readings and QR codes; only water and electricity charges are shown.
- Visitor and pool passes, support tickets with attachments, notification inbox, push notifications, saved payment methods.
- 12 languages with RTL: English, Arabic, German, French, Italian, Russian, Ukrainian, Finnish, Norwegian, Chinese, Hindi, Japanese.

## Structure

```
lib/
  core/          bootstrap (dependency wiring), network (Dio + interceptors), router (GoRouter),
                 localization, theme, shared widgets, services (push), utils
  features/
    auth/        sign-in, resort picker, session and tenant lock
    financial/   charges, payments, receipts, clearance statements
    profile/     profile, units, rentals, payment methods
    support/     tickets, visitor and pool passes
    notifications/
    home/        shell and navigation
test/            widget and bloc tests, with fake repositories
```

Each feature has `data/` (models, repositories) and `presentation/` (bloc, screens, widgets).

**State management is pure BLoC** — events in, states out, no Cubit anywhere. Repositories are interfaces, so every screen is tested against a fake instead of the network.

## Run it

Needs Flutter 3.38 or newer and a running backend (see the main README).

```bash
cp .env.example .env                                              # set API_BASE_URL
cp lib/firebase_options.dart.example lib/firebase_options.dart    # or: flutterfire configure
flutter pub get
flutter run
```

- `.env` is bundled as an asset and `lib/firebase_options.dart` holds your Firebase project's identifiers; both are git-ignored. Android additionally needs `android/app/google-services.json` from your own Firebase project.
- On a **real phone**, `API_BASE_URL` must be the computer's LAN address, not `127.0.0.1`, and the firewall must allow port 8000. Alternatively run `adb reverse tcp:8000 tcp:8000` and keep `127.0.0.1` (the reverse drops whenever the adb daemon restarts).
- In debug builds the sign-in screen shows a *Developer Test Sign-In*. It works only against a backend started with `ALLOW_DEV_AUTH_BYPASS=1`, so you can use the app without a Firebase project.

## Tests

```bash
flutter test      # 79 tests
flutter analyze   # no errors or warnings
```

Screens whose layout depends on the app theme are tested under `AppTheme.lightTheme`, not the default Material theme — the theme makes elevated buttons full width, which breaks a button placed inside a `Row`, and only the real theme shows it.

## Notes for contributors

- Newer strings (profile, rentals, payment methods) live in `lib/core/utils/app_localizations_profile.dart`; a language without an entry falls back to English.
- Anything fetched behind authentication (receipts, ID photos, attachments) must go through the app's authenticated Dio client. Handing such a URL to a browser or `Image.network` returns 401.
