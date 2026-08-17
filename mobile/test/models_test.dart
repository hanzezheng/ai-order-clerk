import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/api/models.dart';

void main() {
  test('posting 三字不进未确认', () {
    expect(postingLabel(null), '');
    expect(postingLabel('pending'), '排队中');
    expect(postingLabel('posted'), '已进草稿');
    expect(postingLabel('unavailable'), '看不见');
  });

  test('好了不再 expect_more', () {
    expect(expectMoreFor('好了'), isFalse);
    expect(expectMoreFor('开李老板的单苹果二十箱'), isTrue);
  });

  test('从 label 拆商品和规格', () {
    const line = DraftLine(
      lineId: '1',
      label: '红富士80果一级烟台箱装',
      qty: '20',
      uom: '箱',
      priceStatus: 'tbd',
      lineStatus: 'ready',
    );
    expect(line.product, '苹果');
    expect(line.spec, '80果');
    expect(line.qtyText, '20箱');
    expect(line.priceTbd, isTrue);
  });

  test('客户显示别名', () {
    const customer = DraftCustomer(name: '李记果行', aliases: ['李老板']);
    expect(customer.displayName, '李老板');
  });
}
