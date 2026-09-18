class ApiEndpoints {
  static const String activate = "/api/auth/activate/";
  static const String firebaseAuth = "/api/auth/firebase/";
  static const String tokenObtain = "/api/auth/token/";
  static const String tokenRefresh = "/api/auth/token/refresh/";
  static const String me = "/api/me/";

  static const String charges = "/api/charges/";
  static const String payments = "/api/payments/";
  static const String initiatePayment = "/api/payments/initiate/";

  static const String tickets = "/api/owner/tickets/";
  static String ticketMessages(int ticketId) => "/api/owner/tickets/$ticketId/messages/";
  static const String passes = "/api/owner/passes/";
}
