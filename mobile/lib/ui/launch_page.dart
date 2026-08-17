import 'package:flutter/material.dart';

import '../api/discovery.dart';
import '../stall/stall_binding.dart';
import 'stall_bind_page.dart';

class LaunchPage extends StatefulWidget {
  const LaunchPage({
    super.key,
    required this.finder,
    required this.onBound,
  });

  final LanClerkFinder finder;
  final Future<void> Function(StallBinding binding) onBound;

  @override
  State<LaunchPage> createState() => _LaunchPageState();
}

class _LaunchPageState extends State<LaunchPage> {
  var _searching = true;
  String? _apiBase;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    setState(() {
      _searching = true;
      _error = null;
    });
    final found = await widget.finder.find();
    if (!mounted) {
      return;
    }
    setState(() {
      _searching = false;
      _apiBase = found;
      _error = found == null ? '电脑上的开单服务还没打开。' : null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_searching) {
      return const Scaffold(
        body: SafeArea(
          child: Padding(
            padding: EdgeInsets.fromLTRB(24, 48, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('今日开单', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800)),
                SizedBox(height: 16),
                Text('正在找开单服务…', style: TextStyle(fontSize: 20, color: Color(0xFF5C675E))),
              ],
            ),
          ),
        ),
      );
    }
    if (_apiBase == null) {
      return Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('今日开单', style: Theme.of(context).textTheme.headlineLarge),
                const SizedBox(height: 16),
                Text(_error ?? '电脑上的开单服务还没打开。', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 12),
                const Text(
                  '先在电脑上打开「启动开单」。手机和电脑要在同一个 Wi-Fi。',
                  style: TextStyle(fontSize: 18, color: Color(0xFF5C675E), height: 1.4),
                ),
                const Spacer(),
                SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: FilledButton(
                    onPressed: _search,
                    child: const Text('再找一次', style: TextStyle(fontSize: 20)),
                  ),
                ),
                const SizedBox(height: 12),
                _ManualConnect(onConnected: (url) => setState(() => _apiBase = url)),
              ],
            ),
          ),
        ),
      );
    }
    return StallBindPage(apiBase: _apiBase!, onBound: widget.onBound);
  }
}

class _ManualConnect extends StatefulWidget {
  const _ManualConnect({required this.onConnected});

  final void Function(String apiBase) onConnected;

  @override
  State<_ManualConnect> createState() => _ManualConnectState();
}

class _ManualConnectState extends State<_ManualConnect> {
  var _open = false;
  final _api = TextEditingController();

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_open) {
      return TextButton(
        onPressed: () => setState(() => _open = true),
        child: const Text('连不上？填电脑上显示的地址'),
      );
    }
    return Column(
      children: [
        TextField(
          controller: _api,
          style: Theme.of(context).textTheme.bodyMedium,
          decoration: const InputDecoration(
            labelText: '电脑上显示的地址',
            hintText: 'http://192.168.1.23:8000',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: () {
              final url = _api.text.trim().replaceAll(RegExp(r'/$'), '');
              if (url.startsWith('http')) {
                widget.onConnected(url);
              }
            },
            child: const Text('用这个地址'),
          ),
        ),
      ],
    );
  }
}
