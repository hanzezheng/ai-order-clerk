import 'package:flutter/material.dart';

import '../api/models.dart';
import '../state/order_book_controller.dart';

class OrderBookPage extends StatefulWidget {
  const OrderBookPage({super.key, required this.controller});

  final OrderBookController controller;

  @override
  State<OrderBookPage> createState() => _OrderBookPageState();
}

class _OrderBookPageState extends State<OrderBookPage> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChange);
    widget.controller.bootstrap();
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChange);
    super.dispose();
  }

  void _onChange() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final draft = c.currentDraft;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                children: [
                  _Header(controller: c),
                  const SizedBox(height: 18),
                  _Reply(text: c.replyText, error: c.errorText, overlay: c.overlay),
                  const SizedBox(height: 16),
                  _CurrentCard(controller: c, draft: draft),
                  const SizedBox(height: 16),
                  _TaskList(title: '待确认', tasks: c.book.pending, empty: '没有其他待确认', onTap: c.selectPending),
                  const SizedBox(height: 12),
                  _TaskList(title: '已确认', tasks: c.book.confirmed, empty: '今天还没有定下的单', confirmed: true),
                ],
              ),
            ),
            _Dock(controller: c),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.controller});

  final OrderBookController controller;

  @override
  Widget build(BuildContext context) {
    final invisible = [
      for (final task in controller.book.confirmed)
        if (task.posting == 'unavailable') task,
    ].length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: Text('今日开单', style: Theme.of(context).textTheme.headlineLarge)),
            Text(
              formatBusinessDate(controller.book.businessDate),
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: const Color(0xFF5C675E)),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          '${controller.stall.stallName}  ·  今天 ${controller.book.todayCount} 张  ·  待确认 ${[
            for (final task in controller.book.tasks)
              if (!task.isConfirmed && task.hasWork) task,
          ].length}  ·  已确认 ${controller.book.confirmed.length}',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (invisible > 0)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('入账看不见 $invisible', style: const TextStyle(color: Color(0xFF9A6B00), fontSize: 16)),
          ),
      ],
    );
  }
}

class _Reply extends StatelessWidget {
  const _Reply({required this.text, required this.error, required this.overlay});

  final String text;
  final String error;
  final String overlay;

  @override
  Widget build(BuildContext context) {
    final shown = error.isNotEmpty ? error : (text.isNotEmpty ? text : (overlay.isNotEmpty ? overlay : '按住说话，喊这一单。'));
    return Text(
      shown,
      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            color: error.isNotEmpty ? const Color(0xFF9A2B2B) : const Color(0xFF1B241C),
          ),
    );
  }
}

class _CurrentCard extends StatelessWidget {
  const _CurrentCard({required this.controller, required this.draft});

  final OrderBookController controller;
  final DraftOrder? draft;

  @override
  Widget build(BuildContext context) {
    final empty = draft == null || draft!.isEmpty;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF1F7A4D), width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('当前订单', style: TextStyle(letterSpacing: 1.4, color: Color(0xFF5C675E), fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text(controller.currentStatusLabel, style: const TextStyle(fontSize: 16, color: Color(0xFFC9A227), fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          if (empty)
            const Text('还没有开始开单', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700))
          else ...[
            Text(draft!.customer?.displayName.isNotEmpty == true ? draft!.customer!.displayName : '客户还没认清',
                style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            for (final line in draft!.lines) _LineRow(line: line),
          ],
        ],
      ),
    );
  }
}

class _LineRow extends StatelessWidget {
  const _LineRow({required this.line});

  final DraftLine line;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(line.product, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                if (line.spec.isNotEmpty)
                  Text(line.spec, style: const TextStyle(fontSize: 16, color: Color(0xFF5C675E))),
              ],
            ),
          ),
          Text(line.qtyText, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
          if (line.priceTbd)
            const Padding(
              padding: EdgeInsets.only(left: 8),
              child: Text('价未定', style: TextStyle(color: Color(0xFFC9A227), fontWeight: FontWeight.w700)),
            ),
        ],
      ),
    );
  }
}

class _TaskList extends StatelessWidget {
  const _TaskList({
    required this.title,
    required this.tasks,
    required this.empty,
    this.confirmed = false,
    this.onTap,
  });

  final String title;
  final List<WorkbenchTask> tasks;
  final String empty;
  final bool confirmed;
  final Future<void> Function(String sessionId)? onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(letterSpacing: 1.4, color: Color(0xFF5C675E), fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        if (tasks.isEmpty)
          Text(empty, style: const TextStyle(color: Color(0xFF5C675E), fontSize: 16))
        else
          for (final task in tasks)
            InkWell(
              onTap: confirmed || onTap == null ? null : () => onTap!(task.sessionId),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${task.customerLabel ?? '未认客户'}  ·  ${task.lineCount}行',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
                    ),
                    Text(
                      confirmed ? (postingLabel(task.posting).isEmpty ? '已确认' : postingLabel(task.posting)) : '待确认',
                      style: TextStyle(
                        fontSize: 16,
                        color: confirmed ? const Color(0xFF1F7A4D) : const Color(0xFFC9A227),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
      ],
    );
  }
}

class _Dock extends StatelessWidget {
  const _Dock({required this.controller});

  final OrderBookController controller;

  @override
  Widget build(BuildContext context) {
    final done = controller.phase == BookPhase.done || (controller.currentDraft?.isConfirmed ?? false);
    final listening = controller.phase == BookPhase.listening;
    final busy = controller.phase == BookPhase.processing;
    return Material(
      color: Colors.white,
      elevation: 8,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Row(
            children: [
              Expanded(
                child: GestureDetector(
                  onTapDown: busy ? null : (_) => controller.beginHold(),
                  onTapUp: busy ? null : (_) => controller.endHold(),
                  onTapCancel: busy ? null : controller.endHold,
                  child: Container(
                    height: 64,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: listening ? const Color(0xFF9A2B2B) : const Color(0xFF1F7A4D),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Text(
                      busy
                          ? '正在写…'
                          : listening
                              ? '正在听…'
                              : done
                                  ? '再开一单'
                                  : '按住说话',
                      style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                height: 64,
                child: FilledButton(
                  onPressed: busy || done ? null : controller.confirmDone,
                  style: FilledButton.styleFrom(backgroundColor: const Color(0xFF1B241C)),
                  child: const Text('好了', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
