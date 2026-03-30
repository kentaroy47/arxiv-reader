import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/paper.dart';

class PaperDetailScreen extends StatelessWidget {
  final Paper paper;
  const PaperDetailScreen({super.key, required this.paper});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final score = paper.score;
    final scoreColor = score >= 0.8
        ? Colors.green
        : score >= 0.6
            ? Colors.orange
            : Colors.grey;

    return Scaffold(
      appBar: AppBar(
        title: const Text('論文詳細'),
        actions: [
          IconButton(
            icon: const Icon(Icons.open_in_new),
            tooltip: 'arxiv で開く',
            onPressed: () => launchUrl(Uri.parse(paper.arxivUrl)),
          ),
          if (paper.pdfUrl != null)
            IconButton(
              icon: const Icon(Icons.picture_as_pdf),
              tooltip: 'PDF',
              onPressed: () => launchUrl(Uri.parse(paper.pdfUrl!)),
            ),
        ],
      ),
      body: SelectionArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // スコア + 日付
              Row(
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: scoreColor.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: scoreColor.withOpacity(0.4)),
                    ),
                    child: Text(
                      '関連度 ${(score * 100).round()}%',
                      style: TextStyle(
                          color: scoreColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 15),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(paper.publishedDate,
                      style: theme.textTheme.bodySmall),
                ],
              ),
              const SizedBox(height: 16),

              // タイトル
              Text(paper.title,
                  style: theme.textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),

              // 著者
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: paper.authors
                    .map((a) => Chip(
                          label: Text(a,
                              style: const TextStyle(fontSize: 12)),
                          padding: EdgeInsets.zero,
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                        ))
                    .toList(),
              ),
              const SizedBox(height: 10),

              // カテゴリ
              Wrap(
                spacing: 6,
                children: paper.categories
                    .map((c) => ActionChip(
                          label: Text(c),
                          onPressed: () {},
                        ))
                    .toList(),
              ),
              const SizedBox(height: 16),

              // スコア理由
              if (paper.scoreReason.isNotEmpty) ...[
                _Header('スコア評価理由'),
                Card(
                  color: scoreColor.withOpacity(0.05),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(paper.scoreReason),
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // 日本語要約
              _Header('日本語要約'),
              if (paper.summary != null && paper.summary!.isNotEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: MarkdownBody(data: paper.summary!),
                  ),
                )
              else
                Card(
                  color: theme.colorScheme.surfaceContainerHighest,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('要約はまだ生成されていません。'),
                        const SizedBox(height: 8),
                        Text(
                          'ローカルサーバーで以下を実行してください:',
                          style: theme.textTheme.bodySmall,
                        ),
                        const SizedBox(height: 4),
                        SelectableText(
                          'python main.py --run-now',
                          style: const TextStyle(
                              fontFamily: 'monospace',
                              color: Colors.blueGrey),
                        ),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: 16),

              // アブストラクト
              _Header('アブストラクト'),
              Text(paper.abstract, style: theme.textTheme.bodyMedium),
              const SizedBox(height: 24),

              // リンク
              Wrap(
                spacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: () => launchUrl(Uri.parse(paper.arxivUrl)),
                    icon: const Icon(Icons.link),
                    label: const Text('arxiv で見る'),
                  ),
                  if (paper.pdfUrl != null)
                    OutlinedButton.icon(
                      onPressed: () => launchUrl(Uri.parse(paper.pdfUrl!)),
                      icon: const Icon(Icons.picture_as_pdf),
                      label: const Text('PDF'),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final String text;
  const _Header(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.primary,
            ),
      ),
    );
  }
}
