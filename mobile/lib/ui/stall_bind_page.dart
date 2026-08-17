import 'package:flutter/material.dart';

import '../stall/stall_binding.dart';

class StallBindPage extends StatefulWidget {
  const StallBindPage({super.key, required this.onBound, this.initialApiBase = 'http://127.0.0.1:8000'});

  final Future<void> Function(StallBinding binding) onBound;
  final String initialApiBase;

  @override
  State<StallBindPage> createState() => _StallBindPageState();
}

class _StallBindPageState extends State<StallBindPage> {
  late final _stall = TextEditingController();
  late final _api = TextEditingController(text: widget.initialApiBase);

  @override
  void dispose() {
    _stall.dispose();
    _api.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _stall.text.trim();
    final api = _api.text.trim();
    if (name.isEmpty || api.isEmpty) {
      return;
    }
    await widget.onBound(StallBinding(stallName: name, apiBase: api));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 36, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('这个手机绑哪个档口？', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 12),
              Text(
                '一个老板对应一个档口。不是登录中台，不是客户管理。',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: const Color(0xFF5C675E)),
              ),
              const SizedBox(height: 28),
              TextField(
                controller: _stall,
                autofocus: true,
                style: Theme.of(context).textTheme.bodyLarge,
                decoration: const InputDecoration(
                  labelText: '档口',
                  hintText: '例如 3号档',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _api,
                style: Theme.of(context).textTheme.bodyMedium,
                decoration: const InputDecoration(
                  labelText: '开单服务地址',
                  hintText: 'http://127.0.0.1:8000',
                  border: OutlineInputBorder(),
                ),
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                height: 56,
                child: FilledButton(
                  onPressed: _submit,
                  child: const Text('开始开单', style: TextStyle(fontSize: 20)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
