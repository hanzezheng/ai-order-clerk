import 'package:flutter/material.dart';

import '../stall/stall_binding.dart';

class StallBindPage extends StatefulWidget {
  const StallBindPage({
    super.key,
    required this.onBound,
    required this.apiBase,
  });

  final Future<void> Function(StallBinding binding) onBound;
  final String apiBase;

  @override
  State<StallBindPage> createState() => _StallBindPageState();
}

class _StallBindPageState extends State<StallBindPage> {
  late final _stall = TextEditingController();

  @override
  void dispose() {
    _stall.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _stall.text.trim();
    if (name.isEmpty) {
      return;
    }
    await widget.onBound(StallBinding(stallName: name, apiBase: widget.apiBase));
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
              Text('这个手机帮哪个档口开单？', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 12),
              const Text(
                '写上档口名就能开始喊。一张单喊完再开下一张。',
                style: TextStyle(fontSize: 18, color: Color(0xFF5C675E), height: 1.4),
              ),
              const SizedBox(height: 28),
              TextField(
                controller: _stall,
                autofocus: true,
                style: Theme.of(context).textTheme.bodyLarge,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _submit(),
                decoration: const InputDecoration(
                  labelText: '档口',
                  hintText: '例如 3号档',
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
