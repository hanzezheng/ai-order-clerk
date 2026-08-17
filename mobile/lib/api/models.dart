class DraftCustomer {
  const DraftCustomer({this.id, this.name, this.stallNo, this.aliases = const []});

  final String? id;
  final String? name;
  final String? stallNo;
  final List<String> aliases;

  String get displayName {
    for (final alias in aliases) {
      if (alias.trim().isNotEmpty) {
        return alias.trim();
      }
    }
    return (name ?? '').trim();
  }

  factory DraftCustomer.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return const DraftCustomer();
    }
    return DraftCustomer(
      id: json['id'] as String?,
      name: json['name'] as String?,
      stallNo: json['stall_no'] as String?,
      aliases: [
        for (final item in (json['aliases'] as List? ?? const []))
          if (item is String) item,
      ],
    );
  }
}

class DraftLine {
  const DraftLine({
    required this.lineId,
    required this.label,
    required this.qty,
    required this.uom,
    required this.priceStatus,
    required this.lineStatus,
  });

  final String lineId;
  final String label;
  final String qty;
  final String uom;
  final String priceStatus;
  final String lineStatus;

  bool get priceTbd => priceStatus == 'tbd';

  String get product {
    if (label.contains('梨')) {
      return '梨';
    }
    if (label.contains('榴莲')) {
      return '榴莲';
    }
    if (label.contains('苹果') || label.contains('富士')) {
      return '苹果';
    }
    return label;
  }

  String get spec {
    final match = RegExp(r'(\d+\s*果|八十果|八零果)').firstMatch(label);
    if (match == null) {
      return '';
    }
    var spec = match.group(1)!.replaceAll(RegExp(r'\s+'), '');
    if (spec == '八十果' || spec == '八零果') {
      spec = '80果';
    }
    return spec;
  }

  String get qtyText => '$qty$uom';

  factory DraftLine.fromJson(Map<String, dynamic> json) {
    return DraftLine(
      lineId: json['line_id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      qty: '${json['qty'] ?? ''}',
      uom: json['uom'] as String? ?? '',
      priceStatus: json['price_status'] as String? ?? '',
      lineStatus: json['line_status'] as String? ?? '',
    );
  }
}

class DraftOrder {
  const DraftOrder({
    required this.orderId,
    required this.status,
    this.customer,
    this.lines = const [],
  });

  final String orderId;
  final String status;
  final DraftCustomer? customer;
  final List<DraftLine> lines;

  bool get isConfirmed => status == 'confirmed';
  bool get isEmpty => (customer == null || customer!.displayName.isEmpty) && lines.isEmpty;

  factory DraftOrder.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return const DraftOrder(orderId: '', status: 'draft');
    }
    final customerJson = json['customer'];
    return DraftOrder(
      orderId: json['order_id'] as String? ?? '',
      status: json['status'] as String? ?? 'draft',
      customer: customerJson is Map<String, dynamic> ? DraftCustomer.fromJson(customerJson) : null,
      lines: [
        for (final item in (json['lines'] as List? ?? const []))
          if (item is Map<String, dynamic>) DraftLine.fromJson(item),
      ],
    );
  }
}

class WorkbenchTask {
  const WorkbenchTask({
    required this.sessionId,
    required this.orderId,
    required this.status,
    this.customerLabel,
    this.lineCount = 0,
    this.pricesIncomplete,
    this.posting,
  });

  final String sessionId;
  final String orderId;
  final String status;
  final String? customerLabel;
  final int lineCount;
  final bool? pricesIncomplete;
  final String? posting;

  bool get isConfirmed => status == 'confirmed';
  bool get hasWork => isConfirmed || (customerLabel != null && customerLabel!.isNotEmpty) || lineCount > 0;

  factory WorkbenchTask.fromJson(Map<String, dynamic> json) {
    return WorkbenchTask(
      sessionId: json['session_id'] as String? ?? '',
      orderId: json['order_id'] as String? ?? '',
      status: json['status'] as String? ?? 'drafting',
      customerLabel: json['customer_label'] as String?,
      lineCount: json['line_count'] as int? ?? 0,
      pricesIncomplete: json['prices_incomplete'] as bool?,
      posting: json['posting'] as String?,
    );
  }
}

class WorkbenchSnapshot {
  const WorkbenchSnapshot({
    required this.businessDate,
    this.currentSessionId,
    this.tasks = const [],
  });

  final String businessDate;
  final String? currentSessionId;
  final List<WorkbenchTask> tasks;

  WorkbenchTask? get current {
    if (currentSessionId == null) {
      return null;
    }
    for (final task in tasks) {
      if (task.sessionId == currentSessionId) {
        return task;
      }
    }
    return null;
  }

  List<WorkbenchTask> get pending => [
        for (final task in tasks)
          if (!task.isConfirmed && task.hasWork && task.sessionId != currentSessionId) task,
      ];

  List<WorkbenchTask> get confirmed => [
        for (final task in tasks)
          if (task.isConfirmed) task,
      ];

  int get todayCount => [
        for (final task in tasks)
          if (task.hasWork) task,
      ].length;

  factory WorkbenchSnapshot.fromJson(Map<String, dynamic> json) {
    return WorkbenchSnapshot(
      businessDate: json['business_date'] as String? ?? '',
      currentSessionId: json['current_session_id'] as String?,
      tasks: [
        for (final item in (json['tasks'] as List? ?? const []))
          if (item is Map<String, dynamic>) WorkbenchTask.fromJson(item),
      ],
    );
  }
}

class TurnResult {
  const TurnResult({
    required this.sessionId,
    required this.replyText,
    required this.confirmOk,
    required this.draft,
    this.posting,
    this.ignored = false,
  });

  final String sessionId;
  final String replyText;
  final bool confirmOk;
  final DraftOrder draft;
  final String? posting;
  final bool ignored;

  factory TurnResult.fromJson(Map<String, dynamic> json) {
    final verdict = json['verdict'];
    final enterprise = json['enterprise'];
    return TurnResult(
      sessionId: json['session_id'] as String? ?? '',
      replyText: json['reply_text'] as String? ?? '',
      confirmOk: verdict is Map<String, dynamic> && verdict['confirm_ok'] == true,
      draft: DraftOrder.fromJson(json['draft'] as Map<String, dynamic>?),
      posting: enterprise is Map<String, dynamic> ? enterprise['posting'] as String? : null,
      ignored: json['ignored'] == true,
    );
  }
}

class SessionSnapshot {
  const SessionSnapshot({
    required this.sessionId,
    required this.status,
    required this.draft,
    this.posting,
  });

  final String sessionId;
  final String status;
  final DraftOrder draft;
  final String? posting;

  factory SessionSnapshot.fromJson(Map<String, dynamic> json) {
    final enterprise = json['enterprise'];
    return SessionSnapshot(
      sessionId: json['session_id'] as String? ?? '',
      status: json['status'] as String? ?? '',
      draft: DraftOrder.fromJson(json['draft'] as Map<String, dynamic>?),
      posting: enterprise is Map<String, dynamic> ? enterprise['posting'] as String? : null,
    );
  }
}

String postingLabel(String? posting) {
  switch (posting) {
    case 'pending':
      return '排队中';
    case 'posted':
      return '已进草稿';
    case 'unavailable':
      return '看不见';
    default:
      return '';
  }
}

String formatBusinessDate(String iso) {
  final parts = iso.split('-');
  if (parts.length < 3) {
    return iso;
  }
  return '${int.parse(parts[1])}月${int.parse(parts[2])}日';
}

bool expectMoreFor(String text) {
  const closers = {'好了', '就这样', '可以了', '定了'};
  final stripped = text.trim();
  if (closers.contains(stripped)) {
    return false;
  }
  return !closers.any(stripped.contains);
}
