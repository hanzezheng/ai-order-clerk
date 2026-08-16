from __future__ import annotations

import json
from os import environ
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from app.erpnext.correlation import InMemoryCorrelationStore
from app.erpnext.ports import (
    CUSTOMER_DOCTYPE,
    ITEM_DOCTYPE,
    SALES_ORDER_DOCTYPE,
    ErpCustomerDraft,
    ErpGatewayError,
    ErpItemDraft,
    ErpSalesOrderDraft,
    customer_erp_name,
    item_code_for,
    sales_order_name_for,
)


class HttpErpGateway:
    """Optional live ERPNext. CI must not set ERPNEXT_URL. Never submits, never sends warehouse."""

    def __init__(
        self,
        url: str,
        *,
        api_key: str = "",
        api_secret: str = "",
        timeout: float = 8.0,
        maps: InMemoryCorrelationStore | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.maps = maps or InMemoryCorrelationStore()
        self.sent: list[dict] = []

    def ensure_customer(self, draft: ErpCustomerDraft) -> str:
        existing = self.maps.customer(draft.runtime_customer_id)
        if existing is not None:
            return existing
        name = customer_erp_name(draft.runtime_customer_id)
        found = self._find(CUSTOMER_DOCTYPE, "runtime_customer_id", str(draft.runtime_customer_id))
        if found:
            self.maps.put_customer(draft.runtime_customer_id, found)
            return found
        created = self._insert(
            CUSTOMER_DOCTYPE,
            {
                "doctype": CUSTOMER_DOCTYPE,
                "name": name,
                "customer_name": draft.customer_name,
                "customer_type": "Company",
                "runtime_customer_id": str(draft.runtime_customer_id),
                "stall_no": draft.stall_no,
            },
        )
        mapped = created or name
        self.maps.put_customer(draft.runtime_customer_id, mapped)
        return mapped

    def ensure_item(self, draft: ErpItemDraft) -> str:
        existing = self.maps.item(draft.runtime_sku_id)
        if existing is not None:
            return existing
        code = item_code_for(draft.runtime_sku_id)
        found = self._find(ITEM_DOCTYPE, "item_code", code)
        if found:
            self.maps.put_item(draft.runtime_sku_id, found)
            return found
        created = self._insert(
            ITEM_DOCTYPE,
            {
                "doctype": ITEM_DOCTYPE,
                "item_code": code,
                "item_name": draft.item_name,
                "stock_uom": draft.stock_uom,
                "is_stock_item": 0,
                "runtime_sku_id": str(draft.runtime_sku_id),
            },
        )
        mapped = created or code
        self.maps.put_item(draft.runtime_sku_id, mapped)
        return mapped

    def ensure_sales_order(
        self,
        draft: ErpSalesOrderDraft,
        *,
        customer: str,
        item_codes: dict[UUID, str],
    ) -> str:
        existing = self.maps.order(draft.runtime_order_id)
        if existing is not None:
            return existing
        name = sales_order_name_for(draft.runtime_order_id)
        found = self._find(SALES_ORDER_DOCTYPE, "runtime_order_id", str(draft.runtime_order_id))
        if found:
            self.maps.put_order(draft.runtime_order_id, found)
            return found
        created = self._insert(
            SALES_ORDER_DOCTYPE,
            {
                "doctype": SALES_ORDER_DOCTYPE,
                "name": name,
                "customer": customer,
                "docstatus": 0,
                "prices_incomplete": draft.prices_incomplete,
                "runtime_order_id": str(draft.runtime_order_id),
                "items": [
                    {
                        "item_code": item_codes[line.runtime_sku_id],
                        "qty": float(line.qty),
                        "uom": line.uom,
                        "rate": float(line.rate),
                    }
                    for line in draft.items
                ],
            },
        )
        mapped = created or name
        self.maps.put_order(draft.runtime_order_id, mapped)
        return mapped

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
        if self.api_key and self.api_secret:
            headers["Authorization"] = f"token {self.api_key}:{self.api_secret}"
        return headers

    def _find(self, doctype: str, field: str, value: str) -> str | None:
        query = urlencode({"filters": json.dumps([[doctype, field, "=", value]])})
        request = Request(f"{self.url}/api/resource/{doctype}?{query}", headers=self._headers(), method="GET")
        body = self._call(request)
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict):
                return str(row.get("name") or row.get("item_code") or "")
        return None

    def _insert(self, doctype: str, payload: dict) -> str:
        self.sent.append(payload)
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.url}/api/resource/{doctype}",
            data=raw,
            headers=self._headers(),
            method="POST",
        )
        body = self._call(request)
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            return str(data.get("name") or data.get("item_code") or payload.get("name") or payload.get("item_code") or "")
        return str(payload.get("name") or payload.get("item_code") or "")

    def _call(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise ErpGatewayError(f"http_{exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ErpGatewayError("erp_unavailable") from exc
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ErpGatewayError("erp_bad_json") from exc
        return parsed if isinstance(parsed, dict) else {}


def live_gateway_from_env() -> HttpErpGateway | None:
    url = environ.get("ERPNEXT_URL", "").strip()
    if not url:
        return None
    return HttpErpGateway(
        url,
        api_key=environ.get("ERPNEXT_API_KEY", "").strip(),
        api_secret=environ.get("ERPNEXT_API_SECRET", "").strip(),
    )
