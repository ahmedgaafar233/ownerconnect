class ApiEndpoints {
  static const String activate = "/api/auth/activate/";
  static const String firebaseAuth = "/api/auth/firebase/";
  static const String tokenObtain = "/api/auth/token/";
  static const String tokenRefresh = "/api/auth/token/refresh/";
  static const String me = "/api/me/";
  static const String resorts = "/api/resorts/";

  static const String charges = "/api/charges/";
  static const String chargesSummary = "/api/charges/summary/";
  static String chargeDefer(int chargeId) => "/api/charges/$chargeId/defer/";
  static const String paymentPlans = "/api/payment-plans/";
  static const String payments = "/api/payments/";
  static const String paymentMethods = "/api/payment-methods/";
  static const String paymentMethodOptions = "/api/payment-methods/options/";
  static String paymentMethod(int id) => "/api/payment-methods/$id/";
  static String paymentMethodDefault(int id) => "/api/payment-methods/$id/default/";
  static const String initiatePayment = "/api/payments/initiate/";
  static const String clearanceGenerate = "/api/clearance/generate/";
  static const String clearanceList = "/api/clearance/";

  static const String tickets = "/api/owner/tickets/";
  static String ticketMessages(int ticketId) => "/api/owner/tickets/$ticketId/messages/";
  static const String passes = "/api/owner/passes/";

  static const String leases = "/api/owner/leases/";
  static String leaseEnd(int id) => "/api/owner/leases/$id/end/";
  static String leaseExtend(int id) => "/api/owner/leases/$id/extend/";
  static String leaseRenew(int id) => "/api/owner/leases/$id/renew/";
  static String leaseAdults(int id) => "/api/owner/leases/$id/adults/";
  static String leaseAdult(int id, int adultId) => "/api/owner/leases/$id/adults/$adultId/";
  static String leaseDocuments(int id) => "/api/owner/leases/$id/documents/";
  static String leaseDocument(int id, int documentId) => "/api/owner/leases/$id/documents/$documentId/";

  static const String notifications = "/api/notifications/";
  static String notificationRead(int id) => "/api/notifications/$id/read/";
  static const String notificationsMarkAllRead = "/api/notifications/mark-all-read/";
  static const String notificationsUnreadCount = "/api/notifications/unread-count/";
}
