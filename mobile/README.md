# 今日开单（Flutter）

农批 AI 销售开单员 V1 的手机壳。老板打开今日开单本、按住喊单、改未确认、点「好了」、看今日张数和入账。

```text
Flutter App → HTTP API → AI Employee Runtime（不改）→ ERPNext Adapter
```

规格：[docs/V1_SALES_CLERK_FLUTTER_APP.md](../docs/V1_SALES_CLERK_FLUTTER_APP.md)。决策：[ADR-037](../docs/ADR/ADR-037-v1-flutter-app.md)。

本目录只做 Input / 工作台壳。不改 Runtime，不做库存 / 财务 / 支付 / CRM。

## 跑起来

后端另开：

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

本机：

```bash
cd mobile
flutter pub get
flutter test
flutter run --dart-define=API_BASE=http://127.0.0.1:8000
```

Android 模拟器把 API 写成 `http://10.0.2.2:8000`。第一次打开先填档口名（一个老板对应一个档口，存在本机）。

打 APK（真机 Android 7.0+）：

```bash
cd mobile
flutter build apk --release --target-platform android-arm64
```

产物：`build/app/outputs/flutter-apk/app-release.apk`。真机第一次打开时把「开单服务地址」填成电脑局域网 IP，例如 `http://192.168.1.23:8000`。
