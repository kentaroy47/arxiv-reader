import 'package:flutter/material.dart';
import '../models/paper.dart';
import '../services/supabase_service.dart';
import '../widgets/paper_card.dart';
import 'paper_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<String> _dates = [];
  String? _selectedDate;
  List<Paper> _papers = [];
  double _minScore = 0.6;
  bool _loading = false;
  String? _error;
  bool _showLogs = false;
  List<Map<String, dynamic>> _logs = [];

  @override
  void initState() {
    super.initState();
    _loadDates();
  }

  Future<void> _loadDates() async {
    setState(() { _loading = true; _error = null; });
    try {
      final dates = await SupabaseService.fetchAvailableDates();
      setState(() {
        _dates = dates;
        _selectedDate = dates.isNotEmpty ? dates.first : null;
      });
      if (_selectedDate != null) await _loadPapers();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadPapers() async {
    if (_selectedDate == null) return;
    setState(() { _loading = true; _error = null; });
    try {
      final papers = await SupabaseService.fetchPapers(
        fetchDate: _selectedDate!,
        minScore: _minScore,
      );
      setState(() => _papers = papers);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _toggleLogs() async {
    if (!_showLogs && _logs.isEmpty) {
      final logs = await SupabaseService.fetchLogs();
      setState(() => _logs = logs);
    }
    setState(() => _showLogs = !_showLogs);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('arxiv Reader'),
        backgroundColor: theme.colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'パイプラインログ',
            onPressed: _toggleLogs,
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: '設定',
            onPressed: () => Navigator.pushNamed(context, '/settings'),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: '更新',
            onPressed: _loading ? null : _loadDates,
          ),
        ],
      ),
      body: Column(
        children: [
          // ログパネル
          if (_showLogs) _LogPanel(logs: _logs),

          // 日付セレクター
          if (_dates.isNotEmpty)
            SizedBox(
              height: 48,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                itemCount: _dates.length,
                separatorBuilder: (_, __) => const SizedBox(width: 6),
                itemBuilder: (_, i) {
                  final d = _dates[i];
                  return ChoiceChip(
                    label: Text(d),
                    selected: d == _selectedDate,
                    onSelected: (_) {
                      setState(() => _selectedDate = d);
                      _loadPapers();
                    },
                  );
                },
              ),
            ),

          // スコアフィルター
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
            child: Row(
              children: [
                Text('閾値: ${(_minScore * 100).round()}%',
                    style: theme.textTheme.bodySmall),
                Expanded(
                  child: Slider(
                    value: _minScore,
                    min: 0.0,
                    max: 1.0,
                    divisions: 20,
                    onChanged: (v) => setState(() => _minScore = v),
                    onChangeEnd: (_) => _loadPapers(),
                  ),
                ),
                Text('${_papers.length} 件',
                    style: theme.textTheme.bodySmall),
              ],
            ),
          ),
          const Divider(height: 1),

          // 論文リスト
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadDates, child: const Text('再試行')),
          ],
        ),
      );
    }
    if (_dates.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('論文データがありません',
                style: TextStyle(color: Colors.grey, fontSize: 16)),
            SizedBox(height: 8),
            Text('ローカルサーバーを起動してパイプラインを実行してください',
                style: TextStyle(color: Colors.grey, fontSize: 12)),
            SizedBox(height: 4),
            Text('python main.py --run-now',
                style: TextStyle(
                    fontFamily: 'monospace',
                    color: Colors.blueGrey,
                    fontSize: 12)),
          ],
        ),
      );
    }
    if (_papers.isEmpty) {
      return const Center(
        child: Text('スコア閾値以上の論文がありません',
            style: TextStyle(color: Colors.grey)),
      );
    }

    return ListView.builder(
      itemCount: _papers.length,
      itemBuilder: (ctx, i) => PaperCard(
        paper: _papers[i],
        onTap: () async {
          await Navigator.push(
            ctx,
            MaterialPageRoute(
                builder: (_) => PaperDetailScreen(paper: _papers[i])),
          );
          // 戻ったとき要約が更新されている可能性があるので再読み込み
          _loadPapers();
        },
      ),
    );
  }
}

class _LogPanel extends StatelessWidget {
  final List<Map<String, dynamic>> logs;
  const _LogPanel({required this.logs});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      constraints: const BoxConstraints(maxHeight: 200),
      color: theme.colorScheme.surfaceContainerHighest,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Text('パイプラインログ',
                style: theme.textTheme.labelLarge?.copyWith(
                    fontWeight: FontWeight.bold)),
          ),
          Expanded(
            child: logs.isEmpty
                ? const Center(child: Text('ログなし'))
                : ListView.builder(
                    itemCount: logs.length,
                    itemBuilder: (_, i) {
                      final log = logs[i];
                      final ok = log['status'] == 'success';
                      return ListTile(
                        dense: true,
                        leading: Icon(
                          ok ? Icons.check_circle : Icons.error,
                          color: ok ? Colors.green : Colors.red,
                          size: 18,
                        ),
                        title: Text(
                          '${log['target_date']} [${log['stage']}] '
                          '${log['papers_processed']} 件',
                          style: theme.textTheme.bodySmall,
                        ),
                        subtitle: log['error_message'] != null
                            ? Text(log['error_message'] as String,
                                style: const TextStyle(
                                    color: Colors.red, fontSize: 11))
                            : null,
                        trailing: Text(
                          (log['run_at'] as String).substring(0, 16),
                          style: theme.textTheme.labelSmall,
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
