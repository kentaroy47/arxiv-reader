class Paper {
  final String arxivId;
  final String title;
  final List<String> authors;
  final String abstract;
  final List<String> categories;
  final String publishedDate;
  final String fetchDate;
  final String arxivUrl;
  final String? pdfUrl;
  final double score;
  final String scoreReason;
  final String? summary;

  const Paper({
    required this.arxivId,
    required this.title,
    required this.authors,
    required this.abstract,
    required this.categories,
    required this.publishedDate,
    required this.fetchDate,
    required this.arxivUrl,
    this.pdfUrl,
    required this.score,
    required this.scoreReason,
    this.summary,
  });

  factory Paper.fromJson(Map<String, dynamic> json) => Paper(
        arxivId: json['arxiv_id'] as String,
        title: json['title'] as String,
        authors: (json['authors'] as List).map((e) => '$e').toList(),
        abstract: json['abstract'] as String? ?? '',
        categories: (json['categories'] as List).map((e) => '$e').toList(),
        publishedDate: json['published_date'] as String? ?? '',
        fetchDate: json['fetch_date'] as String? ?? '',
        arxivUrl: json['arxiv_url'] as String? ?? '',
        pdfUrl: json['pdf_url'] as String?,
        score: (json['score'] as num?)?.toDouble() ?? 0.0,
        scoreReason: json['score_reason'] as String? ?? '',
        summary: json['summary'] as String?,
      );

  Paper copyWith({String? summary}) => Paper(
        arxivId: arxivId,
        title: title,
        authors: authors,
        abstract: abstract,
        categories: categories,
        publishedDate: publishedDate,
        fetchDate: fetchDate,
        arxivUrl: arxivUrl,
        pdfUrl: pdfUrl,
        score: score,
        scoreReason: scoreReason,
        summary: summary ?? this.summary,
      );
}
