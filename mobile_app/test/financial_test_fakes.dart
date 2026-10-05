import 'package:owner_connect/features/financial/data/models/charge_model.dart';
import 'package:owner_connect/features/financial/data/models/charge_summary_model.dart';
import 'package:owner_connect/features/financial/data/models/payment_model.dart';
import 'package:owner_connect/features/financial/data/repositories/financial_repository.dart';

ChargeModel fakeCharge(int id, {String unit = 'DEMO-BELL-1', String type = 'WATER'}) => ChargeModel.fromJson({
      'id': id,
      'unit': 88,
      'unit_key': unit,
      'resort': 1,
      'year': 2026,
      'month': 10,
      'type': type,
      'amount': '60.00',
      'paid_amount': '0.00',
      'remaining_balance': '60.00',
      'is_paid': false,
      'status': 'PUBLISHED',
    });

PaymentModel fakePayment(int id, {String receiptNo = 'REC-DEMO-1', String? url = 'http://host/api/payments/90/receipt/'}) =>
    PaymentModel.fromJson({
      'id': id,
      'unit': 88,
      'unit_key': 'DEMO-BELL-1',
      'resort': 1,
      'receipt_no': receiptNo,
      'receipt_pdf_url': url,
      'total_amount': '120.00',
      'paid_at': '2026-09-19T10:00:00+03:00',
    });

/// In-memory stand-in for the financial API.
class FakeFinancialRepository implements FinancialRepository {
  List<ChargeModel> charges = [];
  List<PaymentModel> payments = [];

  /// URLs the app tried to fetch a PDF from.
  final downloadedUrls = <String>[];

  @override
  Future<List<ChargeModel>> getCharges({
    int page = 1,
    String? type,
    bool? unpaidOnly,
    int? year,
    int? month,
  }) async =>
      charges;

  @override
  Future<ChargeSummaryModel> getChargeSummary() async =>
      const ChargeSummaryModel(totalDue: 60, totalPaid: 0, totalRemaining: 60, byUnit: []);

  @override
  Future<List<PaymentModel>> getPaymentHistory({int page = 1, int? year, int? month}) async => payments;

  @override
  Future<List<int>> downloadFile(String url) async {
    downloadedUrls.add(url);
    // There is no real PDF (or PDF engine) under flutter test.
    throw Exception('no pdf under test');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
