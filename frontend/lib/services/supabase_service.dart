import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/paper.dart';
import '../models/app_settings.dart';

class SupabaseService {
  static SupabaseClient get _db => Supabase.instance.client;

  // ── 論文 ───────────────────────────────────────────────────────────

  static Future<List<Paper>> fetchPapers({
    required String fetchDate,
    double minScore = 0.0,
  }) async {
    final resp = await _db
        .from('papers')
        .select()
        .eq('fetch_date', fetchDate)
        .gte('score', minScore)
        .order('score', ascending: false);
    return (resp as List).map((e) => Paper.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// データが存在する日付一覧 (降順)
  static Future<List<String>> fetchAvailableDates() async {
    final resp = await _db
        .from('papers')
        .select('fetch_date')
        .order('fetch_date', ascending: false);
    final dates = (resp as List)
        .map((e) => e['fetch_date'] as String)
        .toSet()
        .toList()
      ..sort((a, b) => b.compareTo(a));
    return dates;
  }

  static Future<void> updateSummary(String arxivId, String summary) async {
    await _db.from('papers').update({'summary': summary}).eq('arxiv_id', arxivId);
  }

  // ── 設定 ───────────────────────────────────────────────────────────

  static Future<AppSettings> fetchSettings() async {
    final resp =
        await _db.from('user_settings').select().eq('id', 1).maybeSingle();
    if (resp == null) return AppSettings.defaults();
    return AppSettings.fromJson(resp as Map<String, dynamic>);
  }

  static Future<void> saveSettings(AppSettings settings) async {
    await _db.from('user_settings').upsert({'id': 1, ...settings.toJson()});
  }

  // ── パイプラインログ ────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> fetchLogs({int limit = 30}) async {
    final resp = await _db
        .from('pipeline_logs')
        .select()
        .order('run_at', ascending: false)
        .limit(limit);
    return (resp as List).cast<Map<String, dynamic>>();
  }
}
