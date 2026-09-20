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
  static const String initiatePayment = "/api/payments/initiate/";
  static const String clearanceGenerate = "/api/clearance/generate/";
  static const String clearanceList = "/api/clearance/";

  static const String tickets = "/api/owner/tickets/";
  static String ticketMessages(int ticketId) => "/api/owner/tickets/$ticketId/messages/";
  static const String passes = "/api/owner/passes/";

  static const String notifications = "/api/notifications/";
  static String notificationRead(int id) => "/api/notifications/$id/read/";
  static const String notificationsMarkAllRead = "/api/notifications/mark-all-read/";
  static const String notificationsUnreadCount = "/api/notifications/unread-count/";
}
