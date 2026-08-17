import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api/clerk_api.dart';
import 'stall/stall_binding.dart';
import 'state/order_book_controller.dart';
import 'ui/order_book_page.dart';
import 'ui/stall_bind_page.dart';
import 'ui/theme.dart';
import 'voice/device_speech.dart';
import 'voice/speech_ports.dart';

const defaultApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: 'http://127.0.0.1:8000',
);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  runApp(SalesClerkApp(prefs: prefs));
}

class PrefsStallStore implements StallStore {
  PrefsStallStore(this.prefs);

  final SharedPreferences prefs;
  static const _key = 'stall_binding_v1';

  @override
  Future<StallBinding?> load() async => StallBinding.tryParse(prefs.getString(_key));

  @override
  Future<void> save(StallBinding binding) async {
    await prefs.setString(_key, jsonEncode(binding.toJson()));
  }
}

class SalesClerkApp extends StatefulWidget {
  const SalesClerkApp({
    super.key,
    required this.prefs,
    this.apiFactory,
    this.speech,
    this.tts,
    this.initialBinding,
  });

  final SharedPreferences prefs;
  final ClerkApi Function(String apiBase)? apiFactory;
  final SpeechInput? speech;
  final SpeechOutput? tts;
  final StallBinding? initialBinding;

  @override
  State<SalesClerkApp> createState() => _SalesClerkAppState();
}

class _SalesClerkAppState extends State<SalesClerkApp> {
  late final StallStore _store = PrefsStallStore(widget.prefs);
  StallBinding? _binding;
  var _ready = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final stored = widget.initialBinding ?? await _store.load();
    setState(() {
      _binding = stored;
      _ready = true;
    });
  }

  Future<void> _bind(StallBinding binding) async {
    await _store.save(binding);
    setState(() => _binding = binding);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '今日开单',
      debugShowCheckedModeBanner: false,
      theme: stallTheme,
      home: !_ready
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _binding == null
              ? StallBindPage(initialApiBase: defaultApiBase, onBound: _bind)
              : OrderBookPage(
                  controller: OrderBookController(
                    api: (widget.apiFactory ?? (base) => HttpClerkApi(baseUrl: base))(_binding!.apiBase),
                    stall: _binding!,
                    speech: widget.speech ?? DeviceSpeechInput(),
                    tts: widget.tts ?? DeviceSpeechOutput(),
                  ),
                ),
    );
  }
}
