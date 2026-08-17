import 'package:sales_clerk/api/clerk_api.dart';
import 'package:sales_clerk/api/models.dart';

class FakeClerkApi implements ClerkApi {
  FakeClerkApi();

  WorkbenchSnapshot book = const WorkbenchSnapshot(
    businessDate: '2026-08-17',
    currentSessionId: 's-1',
    tasks: [
      WorkbenchTask(sessionId: 's-1', orderId: 'o-1', status: 'drafting'),
    ],
  );

  DraftOrder draft = const DraftOrder(orderId: 'o-1', status: 'draft');
  final turns = <String>[];
  String? posting;

  @override
  Future<WorkbenchSnapshot> getWorkbench() async => book;

  @override
  Future<WorkbenchSnapshot> createTask() async {
    book = WorkbenchSnapshot(
      businessDate: book.businessDate,
      currentSessionId: 's-1',
      tasks: const [
        WorkbenchTask(sessionId: 's-1', orderId: 'o-1', status: 'drafting'),
      ],
    );
    draft = const DraftOrder(orderId: 'o-1', status: 'draft');
    posting = null;
    return book;
  }

  @override
  Future<WorkbenchSnapshot> setCurrent(String sessionId) async {
    book = WorkbenchSnapshot(
      businessDate: book.businessDate,
      currentSessionId: sessionId,
      tasks: book.tasks,
    );
    return book;
  }

  @override
  Future<SessionSnapshot> getSession(String sessionId) async {
    return SessionSnapshot(
      sessionId: sessionId,
      status: draft.isConfirmed ? 'confirmed' : 'drafting',
      draft: draft,
      posting: posting,
    );
  }

  @override
  Future<TurnResult> postTurn({
    required String sessionId,
    required String text,
    required int seq,
    required String utteranceId,
    String source = 'text',
    bool expectMore = true,
  }) async {
    turns.add(text);
    if (text.contains('好了')) {
      draft = DraftOrder(
        orderId: draft.orderId,
        status: 'confirmed',
        customer: draft.customer,
        lines: draft.lines,
      );
      posting = 'posted';
      book = WorkbenchSnapshot(
        businessDate: book.businessDate,
        currentSessionId: sessionId,
        tasks: [
          WorkbenchTask(
            sessionId: sessionId,
            orderId: draft.orderId,
            status: 'confirmed',
            customerLabel: draft.customer?.displayName,
            lineCount: draft.lines.length,
            posting: posting,
          ),
        ],
      );
      return TurnResult(
        sessionId: sessionId,
        replyText: '记下了，价未定。',
        confirmOk: true,
        draft: draft,
        posting: posting,
      );
    }
    if (text.contains('30')) {
      draft = DraftOrder(
        orderId: draft.orderId,
        status: 'draft',
        customer: draft.customer,
        lines: [
          for (final line in draft.lines)
            DraftLine(
              lineId: line.lineId,
              label: line.label,
              qty: '30',
              uom: line.uom,
              priceStatus: line.priceStatus,
              lineStatus: line.lineStatus,
            ),
        ],
      );
      return TurnResult(sessionId: sessionId, replyText: '苹果改30箱。', confirmOk: false, draft: draft);
    }
    draft = const DraftOrder(
      orderId: 'o-1',
      status: 'draft',
      customer: DraftCustomer(name: '李记果行', aliases: ['李老板']),
      lines: [
        DraftLine(
          lineId: 'l-1',
          label: '红富士80果一级烟台箱装',
          qty: '20',
          uom: '箱',
          priceStatus: 'tbd',
          lineStatus: 'ready',
        ),
      ],
    );
    book = WorkbenchSnapshot(
      businessDate: book.businessDate,
      currentSessionId: sessionId,
      tasks: const [
        WorkbenchTask(
          sessionId: 's-1',
          orderId: 'o-1',
          status: 'drafting',
          customerLabel: '李老板',
          lineCount: 1,
        ),
      ],
    );
    return TurnResult(sessionId: sessionId, replyText: '李老板，苹果按档案红富士80果二十箱。', confirmOk: false, draft: draft);
  }
}
