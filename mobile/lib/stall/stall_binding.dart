import 'dart:convert';

class StallBinding {
  const StallBinding({required this.stallName, required this.apiBase});

  final String stallName;
  final String apiBase;

  StallBinding copyWith({String? stallName, String? apiBase}) {
    return StallBinding(
      stallName: stallName ?? this.stallName,
      apiBase: apiBase ?? this.apiBase,
    );
  }

  Map<String, String> toJson() => {
        'stallName': stallName,
        'apiBase': apiBase,
      };

  static StallBinding fromJson(Map<String, dynamic> json) {
    return StallBinding(
      stallName: (json['stallName'] as String? ?? '').trim(),
      apiBase: (json['apiBase'] as String? ?? '').trim(),
    );
  }

  static StallBinding? tryParse(String? raw) {
    if (raw == null || raw.trim().isEmpty) {
      return null;
    }
    final decoded = jsonDecode(raw);
    if (decoded is! Map<String, dynamic>) {
      return null;
    }
    final binding = fromJson(decoded);
    if (binding.stallName.isEmpty || binding.apiBase.isEmpty) {
      return null;
    }
    return binding;
  }
}

abstract class StallStore {
  Future<StallBinding?> load();
  Future<void> save(StallBinding binding);
}

class MemoryStallStore implements StallStore {
  StallBinding? value;

  @override
  Future<StallBinding?> load() async => value;

  @override
  Future<void> save(StallBinding binding) async {
    value = binding;
  }
}
