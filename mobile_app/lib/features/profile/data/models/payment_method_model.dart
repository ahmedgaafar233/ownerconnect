import 'package:equatable/equatable.dart';

/// A saved way to pay: a mobile wallet, an InstaPay address, or Fawry.
/// Never a card — card details only ever go into the payment provider's own
/// secure form.
class PaymentMethodModel extends Equatable {
  final int id;
  final String kind; // CARD | WALLET | INSTAPAY | FAWRY
  final String label;
  final bool isDefault;

  const PaymentMethodModel({required this.id, required this.kind, required this.label, this.isDefault = false});

  factory PaymentMethodModel.fromJson(Map<String, dynamic> json) => PaymentMethodModel(
        id: json['id'] as int,
        kind: json['kind'] as String? ?? '',
        label: json['label'] as String? ?? '',
        isDefault: json['is_default'] as bool? ?? false,
      );

  @override
  List<Object?> get props => [id, kind, label, isDefault];
}

/// What the server says can be added right now.
class PaymentMethodOptions extends Equatable {
  /// Cards need the payment provider's secure form, which needs the village's
  /// account with it — not available until that is linked.
  final bool cardEnabled;
  final List<WalletProvider> walletProviders;
  final int maxMethods;

  const PaymentMethodOptions({this.cardEnabled = false, this.walletProviders = const [], this.maxMethods = 10});

  factory PaymentMethodOptions.fromJson(Map<String, dynamic> json) {
    final card = json['card'];
    final wallet = json['wallet'];
    return PaymentMethodOptions(
      cardEnabled: card is Map<String, dynamic> && card['enabled'] == true,
      walletProviders: wallet is Map<String, dynamic>
          ? (wallet['providers'] as List? ?? const [])
              .whereType<Map<String, dynamic>>()
              .map((p) => WalletProvider(p['value'] as String? ?? '', p['label'] as String? ?? ''))
              .toList()
          : const [],
      maxMethods: json['max_methods'] as int? ?? 10,
    );
  }

  @override
  List<Object?> get props => [cardEnabled, walletProviders, maxMethods];
}

class WalletProvider extends Equatable {
  final String value;
  final String label;

  const WalletProvider(this.value, this.label);

  @override
  List<Object?> get props => [value, label];
}
