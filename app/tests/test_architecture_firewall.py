from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

POLICY = ROOT / "app/policy"
RESOLVER = ROOT / "app/services/product_resolver.py"
ORDER_SERVICE = ROOT / "app/services/order_service.py"
MEMORY = ROOT / "app/memory"
PARSER_FILES = [
    ROOT / "app/agent/parser.py",
    ROOT / "app/agent/llm_parser.py",
    ROOT / "app/agent/default_parser.py",
    ROOT / "app/agent/llm_schema.py",
    ROOT / "app/agent/llm_convert.py",
    ROOT / "app/agent/turn_parser.py",
]
UNDERSTANDING = ROOT / "app/services/product_understanding.py"

ERP_PREFIXES = ("app.erpnext", "frappe")
DB_PREFIXES = ("app.database", "sqlalchemy", "psycopg", "alembic")
MEMORY_TEXT_NEEDLES = ("user_text", "raw_text", "utterance")


def _py_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _starts_with(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


def test_policy_does_not_import_erp():
    for path in _py_files(POLICY):
        for module in _imported_modules(path):
            assert not _starts_with(module, ERP_PREFIXES), f"{path} imports {module}"


def test_resolver_does_not_query_erp():
    for path in (RESOLVER, UNDERSTANDING):
        text = path.read_text(encoding="utf-8")
        for module in _imported_modules(path):
            assert not _starts_with(module, ERP_PREFIXES), f"{path} imports {module}"
        lowered = text.lower()
        assert "item_code" not in lowered
        assert "frappe" not in lowered
        assert "doctype" not in lowered


def test_order_service_does_not_call_adapter():
    for module in _imported_modules(ORDER_SERVICE):
        assert not _starts_with(module, ERP_PREFIXES), module
        assert module != "app.erpnext.consumer"
        assert module != "app.erpnext.read"
    text = ORDER_SERVICE.read_text(encoding="utf-8")
    assert "ensure_sales_order" not in text
    assert "EnterpriseFactPort" not in text
    assert "ErpnextReadAdapter" not in text


def test_parser_does_not_access_database():
    for path in PARSER_FILES:
        assert path.exists(), path
        for module in _imported_modules(path):
            assert not _starts_with(module, DB_PREFIXES), f"{path} imports {module}"
            assert not _starts_with(module, ERP_PREFIXES), f"{path} imports {module}"


def test_memory_does_not_read_user_text():
    for path in _py_files(MEMORY):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in MEMORY_TEXT_NEEDLES:
                raise AssertionError(f"{path} reads .{node.attr}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in MEMORY_TEXT_NEEDLES:
                raise AssertionError(f"{path} mentions {node.value!r}")
            if isinstance(node, ast.Name) and node.id in MEMORY_TEXT_NEEDLES:
                raise AssertionError(f"{path} uses {node.id}")


def test_confirm_gate_source_has_no_erp_inputs():
    decision = (ROOT / "app/policy/decision.py").read_text(encoding="utf-8")
    assert "def confirm_gate(self, session" in decision
    assert "erpnext" not in decision.lower()
    assert "item_code" not in decision
    assert "warehouse" not in decision
    assert "stock" not in decision.lower()
