import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:psx_scanner/theme.dart';
import 'package:psx_scanner/widgets.dart';

void main() {
  testWidgets('PillBadge renders its text', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: const Scaffold(body: Center(child: PillBadge('BUY', AppColors.green))),
      ),
    );
    expect(find.text('BUY'), findsOneWidget);
  });
}
