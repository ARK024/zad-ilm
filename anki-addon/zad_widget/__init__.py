# -*- coding: utf-8 -*-
"""زاد العلم — ودجت عائم لمراجعة بطاقات أنكي على مدار اليوم.

إضافة لأنكي: تستخدم جدولة أنكي الأصلية والرزم والقوالب والـ Cloze والصوتيات كما هي،
وتُظهر البطاقة المستحقة في نافذة صغيرة عائمة على فترات خلال اليوم.
"""
try:
    from aqt import gui_hooks, mw
except Exception:  # الاختبارات خارج أنكي: لا واجهة Qt
    mw = None

if mw is not None:
    from .controller import Controller

    _ctl = Controller()
    _ctl.start()
    gui_hooks.profile_did_open.append(_ctl.on_profile_open)
    gui_hooks.profile_will_close.append(_ctl.on_profile_close)
