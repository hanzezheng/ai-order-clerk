from __future__ import annotations

from os import environ

# 测试不占局域网发现端口；产品默认仍开启。
environ["CLERK_PRESENCE"] = "0"
