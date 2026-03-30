class AppSettings {
  final List<String> interestKeywords;
  final List<String> interestCategories;
  final double scoreThreshold;
  final int maxResults;
  final String ollamaUrl;
  final String ollamaModel;
  final String notificationType;
  final String? slackWebhookUrl;
  final String? emailTo;
  final String? emailSmtpHost;
  final int emailSmtpPort;
  final String? emailSmtpUser;
  final String? emailSmtpPassword;
  final int scheduleHour;
  final int scheduleMinute;

  const AppSettings({
    required this.interestKeywords,
    required this.interestCategories,
    required this.scoreThreshold,
    required this.maxResults,
    required this.ollamaUrl,
    required this.ollamaModel,
    required this.notificationType,
    this.slackWebhookUrl,
    this.emailTo,
    this.emailSmtpHost,
    required this.emailSmtpPort,
    this.emailSmtpUser,
    this.emailSmtpPassword,
    required this.scheduleHour,
    required this.scheduleMinute,
  });

  factory AppSettings.defaults() => const AppSettings(
        interestKeywords: [],
        interestCategories: ['cs.AI', 'cs.LG'],
        scoreThreshold: 0.6,
        maxResults: 100,
        ollamaUrl: 'http://localhost:11434',
        ollamaModel: 'qwen3:8b',
        notificationType: 'none',
        emailSmtpPort: 587,
        scheduleHour: 8,
        scheduleMinute: 0,
      );

  factory AppSettings.fromJson(Map<String, dynamic> json) => AppSettings(
        interestKeywords:
            (json['interest_keywords'] as List? ?? []).map((e) => '$e').toList(),
        interestCategories:
            (json['interest_categories'] as List? ?? []).map((e) => '$e').toList(),
        scoreThreshold:
            (json['score_threshold'] as num?)?.toDouble() ?? 0.6,
        maxResults: json['max_results'] as int? ?? 100,
        ollamaUrl: json['ollama_url'] as String? ?? 'http://localhost:11434',
        ollamaModel: json['ollama_model'] as String? ?? 'qwen3:8b',
        notificationType: json['notification_type'] as String? ?? 'none',
        slackWebhookUrl: json['slack_webhook_url'] as String?,
        emailTo: json['email_to'] as String?,
        emailSmtpHost: json['email_smtp_host'] as String?,
        emailSmtpPort: json['email_smtp_port'] as int? ?? 587,
        emailSmtpUser: json['email_smtp_user'] as String?,
        emailSmtpPassword: json['email_smtp_password'] as String?,
        scheduleHour: json['schedule_hour'] as int? ?? 8,
        scheduleMinute: json['schedule_minute'] as int? ?? 0,
      );

  Map<String, dynamic> toJson() => {
        'interest_keywords': interestKeywords,
        'interest_categories': interestCategories,
        'score_threshold': scoreThreshold,
        'max_results': maxResults,
        'ollama_url': ollamaUrl,
        'ollama_model': ollamaModel,
        'notification_type': notificationType,
        'slack_webhook_url': slackWebhookUrl,
        'email_to': emailTo,
        'email_smtp_host': emailSmtpHost,
        'email_smtp_port': emailSmtpPort,
        'email_smtp_user': emailSmtpUser,
        'email_smtp_password': emailSmtpPassword,
        'schedule_hour': scheduleHour,
        'schedule_minute': scheduleMinute,
      };

  AppSettings copyWith({
    List<String>? interestKeywords,
    List<String>? interestCategories,
    double? scoreThreshold,
    int? maxResults,
    String? ollamaUrl,
    String? ollamaModel,
    String? notificationType,
    String? slackWebhookUrl,
    String? emailTo,
    String? emailSmtpHost,
    int? emailSmtpPort,
    String? emailSmtpUser,
    String? emailSmtpPassword,
    int? scheduleHour,
    int? scheduleMinute,
  }) =>
      AppSettings(
        interestKeywords: interestKeywords ?? this.interestKeywords,
        interestCategories: interestCategories ?? this.interestCategories,
        scoreThreshold: scoreThreshold ?? this.scoreThreshold,
        maxResults: maxResults ?? this.maxResults,
        ollamaUrl: ollamaUrl ?? this.ollamaUrl,
        ollamaModel: ollamaModel ?? this.ollamaModel,
        notificationType: notificationType ?? this.notificationType,
        slackWebhookUrl: slackWebhookUrl ?? this.slackWebhookUrl,
        emailTo: emailTo ?? this.emailTo,
        emailSmtpHost: emailSmtpHost ?? this.emailSmtpHost,
        emailSmtpPort: emailSmtpPort ?? this.emailSmtpPort,
        emailSmtpUser: emailSmtpUser ?? this.emailSmtpUser,
        emailSmtpPassword: emailSmtpPassword ?? this.emailSmtpPassword,
        scheduleHour: scheduleHour ?? this.scheduleHour,
        scheduleMinute: scheduleMinute ?? this.scheduleMinute,
      );
}
