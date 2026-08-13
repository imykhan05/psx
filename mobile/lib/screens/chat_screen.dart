import 'package:flutter/material.dart';
import '../api.dart';
import '../theme.dart';

class _Msg {
  final String role; // user | ai | err
  final String text;
  _Msg(this.role, this.text);
}

class ChatScreen extends StatefulWidget {
  final ApiService api;
  const ChatScreen({super.key, required this.api});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final controller = TextEditingController();
  final scroll = ScrollController();
  final List<_Msg> messages = [
    _Msg('ai',
        'Local assistant — no external AI, no cost. Poochein (English/Urdu):\n'
        '• market kaisa hai?  • HBL ka haal  • top gainers\n'
        '• value stocks  • kaunse sectors chal rahe  • kya khareedun?'),
  ];
  bool busy = false;

  @override
  void dispose() {
    controller.dispose();
    scroll.dispose();
    super.dispose();
  }

  void _toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (scroll.hasClients) {
        scroll.animateTo(scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _send() async {
    final q = controller.text.trim();
    if (q.isEmpty || busy) return;
    controller.clear();
    setState(() {
      messages.add(_Msg('user', q));
      busy = true;
    });
    _toBottom();
    try {
      final answer = await widget.api.ask(q);   // local assistant, no external AI
      if (mounted) setState(() => messages.add(_Msg('ai', answer)));
    } on ApiException catch (e) {
      if (mounted) setState(() => messages.add(_Msg('err', 'Not reachable: ${e.message}')));
    } finally {
      if (mounted) setState(() => busy = false);
      _toBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            controller: scroll,
            padding: const EdgeInsets.all(14),
            itemCount: messages.length + (busy ? 1 : 0),
            itemBuilder: (context, i) {
              if (busy && i == messages.length) {
                return const _Bubble(role: 'ai', text: '…thinking');
              }
              final m = messages[i];
              return _Bubble(role: m.role, text: m.text);
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  enabled: !busy,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(hintText: 'Type your question…'),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton(onPressed: busy ? null : _send, child: const Text('Send')),
            ],
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  final String role;
  final String text;
  const _Bubble({required this.role, required this.text});

  @override
  Widget build(BuildContext context) {
    final isUser = role == 'user';
    final isErr = role == 'err';
    final align = isUser ? Alignment.centerRight : Alignment.centerLeft;
    final bg = isUser
        ? const Color(0xFF163A5C)
        : isErr
            ? AppColors.red.withValues(alpha: 0.12)
            : AppColors.card;
    final border = isErr ? AppColors.red.withValues(alpha: 0.5) : AppColors.border;
    return Container(
      alignment: align,
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isUser ? Colors.transparent : border),
        ),
        child: Text(text,
            style: TextStyle(color: isErr ? const Color(0xFFFFC2C9) : AppColors.text, fontSize: 14, height: 1.4)),
      ),
    );
  }
}
