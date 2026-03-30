import 'package:flutter/material.dart';
import '../models/app_settings.dart';
import '../services/supabase_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  AppSettings? _s;
  bool _loading = true;
  bool _saving = false;
  final _kwCtrl = TextEditingController();

  // Ollama / SMTP フィールド用コントローラー
  late TextEditingController _ollamaUrlCtrl;
  late TextEditingController _ollamaModelCtrl;
  late TextEditingController _slackCtrl;
  late TextEditingController _emailToCtrl;
  late TextEditingController _smtpHostCtrl;
  late TextEditingController _smtpUserCtrl;
  late TextEditingController _smtpPassCtrl;

  static const _categories = [
    'cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'cs.RO', 'cs.NE',
    'cs.IR', 'cs.HC', 'stat.ML', 'eess.AS', 'eess.IV',
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _kwCtrl.dispose();
    _ollamaUrlCtrl.dispose();
    _ollamaModelCtrl.dispose();
    _slackCtrl.dispose();
    _emailToCtrl.dispose();
    _smtpHostCtrl.dispose();
    _smtpUserCtrl.dispose();
    _smtpPassCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final s = await SupabaseService.fetchSettings();
      _initControllers(s);
      setState(() { _s = s; _loading = false; });
    } catch (_) {
      final s = AppSettings.defaults();
      _initControllers(s);
      setState(() { _s = s; _loading = false; });
    }
  }

  void _initControllers(AppSettings s) {
    _ollamaUrlCtrl = TextEditingController(text: s.ollamaUrl);
    _ollamaModelCtrl = TextEditingController(text: s.ollamaModel);
    _slackCtrl = TextEditingController(text: s.slackWebhookUrl ?? '');
    _emailToCtrl = TextEditingController(text: s.emailTo ?? '');
    _smtpHostCtrl = TextEditingController(text: s.emailSmtpHost ?? 'smtp.gmail.com');
    _smtpUserCtrl = TextEditingController(text: s.emailSmtpUser ?? '');
    _smtpPassCtrl = TextEditingController(text: s.emailSmtpPassword ?? '');
  }

  AppSettings _collectSettings() => _s!.copyWith(
        ollamaUrl: _ollamaUrlCtrl.text,
        ollamaModel: _ollamaModelCtrl.text,
        slackWebhookUrl: _slackCtrl.text.isEmpty ? null : _slackCtrl.text,
        emailTo: _emailToCtrl.text.isEmpty ? null : _emailToCtrl.text,
        emailSmtpHost: _smtpHostCtrl.text.isEmpty ? null : _smtpHostCtrl.text,
        emailSmtpUser: _smtpUserCtrl.text.isEmpty ? null : _smtpUserCtrl.text,
        emailSmtpPassword:
            _smtpPassCtrl.text.isEmpty ? null : _smtpPassCtrl.text,
      );

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await SupabaseService.saveSettings(_collectSettings());
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('設定を保存しました')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存失敗: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      setState(() => _saving = false);
    }
  }

  void _addKeyword(String kw) {
    kw = kw.trim();
    if (kw.isEmpty) return;
    final list = [..._s!.interestKeywords];
    if (!list.contains(kw)) {
      setState(() => _s = _s!.copyWith(interestKeywords: [...list, kw]));
    }
    _kwCtrl.clear();
  }

  void _removeKeyword(String kw) {
    final list = [..._s!.interestKeywords]..remove(kw);
    setState(() => _s = _s!.copyWith(interestKeywords: list));
  }

  void _toggleCategory(String cat) {
    final list = [..._s!.interestCategories];
    list.contains(cat) ? list.remove(cat) : list.add(cat);
    setState(() => _s = _s!.copyWith(interestCategories: list));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('設定'),
        actions: [
          if (!_loading)
            _saving
                ? const Padding(
                    padding: EdgeInsets.all(16),
                    child: SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2)),
                  )
                : TextButton.icon(
                    onPressed: _save,
                    icon: const Icon(Icons.save),
                    label: const Text('保存'),
                  ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _section('興味キーワード', _keywords()),
                _section('arxivカテゴリ', _cats()),
                _section('スコア設定', _score()),
                _section('LLM設定 (Ollama)', _llm()),
                _section('通知設定', _notification()),
                _section('スケジュール', _schedule()),
              ],
            ),
    );
  }

  Widget _section(String title, Widget child) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Text(title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.primary)),
      ),
      child,
      const Divider(height: 28),
    ]);
  }

  Widget _keywords() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
          child: TextField(
            controller: _kwCtrl,
            decoration: const InputDecoration(
              hintText: 'キーワードを入力 (例: reinforcement learning)',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onSubmitted: _addKeyword,
          ),
        ),
        const SizedBox(width: 8),
        FilledButton(
            onPressed: () => _addKeyword(_kwCtrl.text),
            child: const Text('追加')),
      ]),
      const SizedBox(height: 10),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: _s!.interestKeywords
            .map((kw) => Chip(label: Text(kw), onDeleted: () => _removeKeyword(kw)))
            .toList(),
      ),
    ]);
  }

  Widget _cats() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _categories
          .map((c) => FilterChip(
                label: Text(c),
                selected: _s!.interestCategories.contains(c),
                onSelected: (_) => _toggleCategory(c),
              ))
          .toList(),
    );
  }

  Widget _score() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('スコア閾値: ${(_s!.scoreThreshold * 100).round()}%'),
      Slider(
        value: _s!.scoreThreshold,
        min: 0.0, max: 1.0, divisions: 20,
        label: '${(_s!.scoreThreshold * 100).round()}%',
        onChanged: (v) => setState(() => _s = _s!.copyWith(scoreThreshold: v)),
      ),
      Text('最大取得件数: ${_s!.maxResults} 件'),
      Slider(
        value: _s!.maxResults.toDouble(),
        min: 10, max: 500, divisions: 49,
        label: '${_s!.maxResults}',
        onChanged: (v) => setState(() => _s = _s!.copyWith(maxResults: v.round())),
      ),
    ]);
  }

  Widget _llm() {
    return Column(children: [
      TextField(
        controller: _ollamaUrlCtrl,
        decoration: const InputDecoration(
          labelText: 'Ollama URL',
          hintText: 'http://localhost:11434',
          border: OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _ollamaModelCtrl,
        decoration: const InputDecoration(
          labelText: 'モデル名',
          hintText: 'qwen3:8b',
          border: OutlineInputBorder(),
        ),
      ),
    ]);
  }

  Widget _notification() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      DropdownButtonFormField<String>(
        value: _s!.notificationType,
        decoration: const InputDecoration(
          labelText: '通知方法',
          border: OutlineInputBorder(),
        ),
        items: const [
          DropdownMenuItem(value: 'none', child: Text('通知なし')),
          DropdownMenuItem(value: 'slack', child: Text('Slack')),
          DropdownMenuItem(value: 'email', child: Text('メール')),
        ],
        onChanged: (v) => setState(() => _s = _s!.copyWith(notificationType: v)),
      ),
      if (_s!.notificationType == 'slack') ...[
        const SizedBox(height: 12),
        TextField(
          controller: _slackCtrl,
          decoration: const InputDecoration(
            labelText: 'Slack Webhook URL',
            border: OutlineInputBorder(),
          ),
        ),
      ],
      if (_s!.notificationType == 'email') ...[
        const SizedBox(height: 12),
        TextField(controller: _emailToCtrl,
            decoration: const InputDecoration(labelText: '送信先メールアドレス',
                border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _smtpHostCtrl,
            decoration: const InputDecoration(labelText: 'SMTPホスト',
                hintText: 'smtp.gmail.com', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _smtpUserCtrl,
            decoration: const InputDecoration(labelText: 'SMTPユーザー',
                border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(
          controller: _smtpPassCtrl,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'SMTPパスワード',
              border: OutlineInputBorder()),
        ),
      ],
    ]);
  }

  Widget _schedule() {
    return Row(children: [
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          children: [
        Text('時: ${_s!.scheduleHour}'),
        Slider(
          value: _s!.scheduleHour.toDouble(),
          min: 0, max: 23, divisions: 23,
          label: '${_s!.scheduleHour}時',
          onChanged: (v) =>
              setState(() => _s = _s!.copyWith(scheduleHour: v.round())),
        ),
      ])),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          children: [
        Text('分: ${_s!.scheduleMinute}'),
        Slider(
          value: _s!.scheduleMinute.toDouble(),
          min: 0, max: 59, divisions: 59,
          label: '${_s!.scheduleMinute}分',
          onChanged: (v) =>
              setState(() => _s = _s!.copyWith(scheduleMinute: v.round())),
        ),
      ])),
      Text(
        '${_s!.scheduleHour.toString().padLeft(2, '0')}:'
        '${_s!.scheduleMinute.toString().padLeft(2, '0')}',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
    ]);
  }
}
