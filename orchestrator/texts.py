"""All customer-facing text, Arabic + English."""

TEXTS = {
    "choose_lang": {
        "ar": "أهلاً 👋 اختر لغتك / Choose your language:",
        "en": "Hi 👋 اختر لغتك / Choose your language:",
    },
    "menu": {
        "ar": "🎬 <b>{brand}</b>\nإعلانات فيديو قصيرة لمنتجك، جاهزة لإنستغرام وتيك توك، بالذكاء الاصطناعي.\n\nوش تبغى تسوي؟",
        "en": "🎬 <b>{brand}</b>\nShort AI video ads for your product, ready for Instagram and TikTok.\n\nWhat would you like to do?",
    },
    "btn_new": {"ar": "🎬 إعلان جديد", "en": "🎬 New ad"},
    "btn_prices": {"ar": "💰 الأسعار", "en": "💰 Prices"},
    "btn_orders": {"ar": "📋 طلباتي", "en": "📋 My orders"},
    "btn_lang": {"ar": "🌐 English", "en": "🌐 العربية"},
    "prices": {
        "ar": "💰 <b>الأسعار</b> (لكل إعلان، تدفع بعد ما يعجبك):\n{lines}\n\n🎁 أول إعلان لك <b>مجاني</b> للتجربة.\nكل إعلان فيه حتى {rev} تعديلات أو إعادات مجاناً.",
        "en": "💰 <b>Prices</b> (per ad, you pay only after you like it):\n{lines}\n\n🎁 Your first ad is <b>free</b> to try.\nEach ad includes up to {rev} free edits or re-generations.",
    },
    "prices_nofree": {
        "ar": "💰 <b>الأسعار</b> (لكل إعلان، تدفع بعد ما يعجبك):\n{lines}\n\nكل إعلان فيه حتى {rev} تعديلات أو إعادات مجاناً.",
        "en": "💰 <b>Prices</b> (per ad, you pay only after you like it):\n{lines}\n\nEach ad includes up to {rev} free edits or re-generations.",
    },
    "ask_desc": {
        "ar": "✍️ اكتب وصف منتجك في رسالة وحدة:\n• اسم المنتج ووش هو\n• أهم المميزات\n• السعر أو العرض (إن وجد)\n• لمن موجّه\n\nمثال: <i>عطر رجالي «سهم»، ريحة خشبية تدوم ١٢ ساعة، السعر ٩٩ ريال، توصيل مجاني</i>",
        "en": "✍️ Describe your product in one message:\n• Product name and what it is\n• Main features\n• Price or offer (if any)\n• Target audience\n\nExample: <i>“Sahm” men's perfume, woody scent lasting 12 hours, $25, free delivery</i>",
    },
    "desc_short": {"ar": "الوصف قصير شوي، زِد تفاصيل عن المنتج 🙏", "en": "Please add a bit more detail about the product 🙏"},
    "ask_photo": {
        "ar": "📸 أرسل <b>صورة المنتج</b> (تظهر في نهاية الإعلان مع السعر)، أو اضغط تخطي.",
        "en": "📸 Send a <b>product photo</b> (shown at the end with the offer), or tap Skip.",
    },
    "btn_skip": {"ar": "⏭ تخطي", "en": "⏭ Skip"},
    "ask_adlang": {"ar": "🗣 بأي لغة تبغى نصوص الإعلان؟", "en": "🗣 Which language should the ad text be in?"},
    "ask_len": {"ar": "⏱ كم مدة الإعلان؟", "en": "⏱ How long should the ad be?"},
    "len_btn": {"ar": "{sec} ثانية · {price}$", "en": "{sec}s · ${price}"},
    "confirm": {
        "ar": "📝 <b>ملخص الطلب</b>\nالمدة: {sec} ثانية\nلغة الإعلان: {adlang}\nصورة المنتج: {photo}\nالسعر: {price}\n\nنأكد؟",
        "en": "📝 <b>Order summary</b>\nLength: {sec}s\nAd language: {adlang}\nProduct photo: {photo}\nPrice: {price}\n\nConfirm?",
    },
    "free_label": {"ar": "مجاني 🎁 (أول إعلان)", "en": "Free 🎁 (first ad)"},
    "yes": {"ar": "نعم", "en": "Yes"},
    "no": {"ar": "لا", "en": "No"},
    "btn_confirm": {"ar": "✅ تأكيد", "en": "✅ Confirm"},
    "btn_cancel": {"ar": "❌ إلغاء", "en": "❌ Cancel"},
    "cancelled": {"ar": "تم الإلغاء.", "en": "Cancelled."},
    "queued": {
        "ar": "✅ استلمنا طلبك رقم <b>#{oid}</b>.\nبنجهز لك المعاينة ونرسلها هنا، غالباً خلال {eta}. ما يحتاج تسوي شي 🙌",
        "en": "✅ Order <b>#{oid}</b> received.\nWe'll send the preview here, usually within {eta}. Nothing else needed 🙌",
    },
    "eta": {"ar": "١–٣ ساعات", "en": "1–3 hours"},
    "preview_caption": {
        "ar": "🎬 معاينة طلبك <b>#{oid}</b>\nوش رأيك؟",
        "en": "🎬 Preview of order <b>#{oid}</b>\nWhat do you think?",
    },
    "btn_ok": {"ar": "✅ ممتاز", "en": "✅ Perfect"},
    "btn_regen": {"ar": "🔄 إعادة توليد", "en": "🔄 Regenerate"},
    "btn_edit": {"ar": "✏️ تعديل", "en": "✏️ Edit"},
    "ask_edit": {
        "ar": "✏️ اكتب وش تبغى نغيّر في الإعلان (مثلاً: خلّ الخلفية بحر، غيّر النص الأخير، أضف شخص يستخدم المنتج…)",
        "en": "✏️ Tell us what to change (e.g. make the background a beach, change the last text, add a person using it…)",
    },
    "rev_queued": {
        "ar": "👌 تمام، بنجهز نسخة جديدة لطلب #{oid} ونرسلها هنا.\nباقي لك {left} تعديل/إعادة.",
        "en": "👌 Got it, preparing a new version of #{oid}.\nYou have {left} edit(s)/regeneration(s) left.",
    },
    "rev_limit": {
        "ar": "وصلت للحد الأقصى من التعديلات لهذا الطلب. تقدر تعتمد النسخة الحالية ✅ أو تسوي طلباً جديداً.",
        "en": "You've reached the edit limit for this order. You can approve this version ✅ or start a new order.",
    },
    "pay": {
        "ar": ("💳 <b>الدفع لطلب #{oid}</b>\n\nحوّل بالضبط:\n<code>{amount}</code> <b>{token}</b>\n\n"
               "على شبكة: <b>{network}</b>\nإلى العنوان:\n<code>{address}</code>\n\n"
               "⚠️ لازم يكون المبلغ <b>بالضبط {amount}</b> وعلى نفس الشبكة، عشان نتعرف على دفعتك تلقائياً.\n"
               "بعد التحويل ما يحتاج ترسل شي: أول ما توصل الدفعة (عادة خلال ١٠–٢٠ دقيقة) يوصلك الإعلان بدون علامة مائية هنا."),
        "en": ("💳 <b>Payment for order #{oid}</b>\n\nSend exactly:\n<code>{amount}</code> <b>{token}</b>\n\n"
               "Network: <b>{network}</b>\nTo address:\n<code>{address}</code>\n\n"
               "⚠️ The amount must be <b>exactly {amount}</b> on the same network so we can match it automatically.\n"
               "No need to send anything after paying: once it arrives (usually 10–20 min) you'll get the clean ad here."),
    },
    "paid": {
        "ar": "🎉 وصلت دفعتك! هذا إعلانك <b>#{oid}</b> النهائي بدون علامة مائية. شكراً لثقتك 🙏",
        "en": "🎉 Payment received! Here is your final ad <b>#{oid}</b>, no watermark. Thank you 🙏",
    },
    "free_done": {
        "ar": "🎁 هذا إعلانك المجاني <b>#{oid}</b>! إذا عجبك، اطلب إعلانك الجاي من القائمة 👇",
        "en": "🎁 Here is your free ad <b>#{oid}</b>! If you like it, order your next one from the menu 👇",
    },
    "failed": {
        "ar": "😔 صار خلل أثناء تجهيز طلبك #{oid}. بنعيد المحاولة تلقائياً.",
        "en": "😔 Something went wrong preparing #{oid}. We're retrying automatically.",
    },
    "no_orders": {"ar": "ما عندك طلبات للحين.", "en": "You have no orders yet."},
    "orders_list": {"ar": "📋 <b>آخر طلباتك</b>\n{lines}", "en": "📋 <b>Your recent orders</b>\n{lines}"},
    "busy": {"ar": "طلبك هذا قيد التجهيز حالياً ⏳", "en": "This order is being prepared ⏳"},
    "unknown": {"ar": "استخدم الأزرار تحت 👇", "en": "Please use the buttons below 👇"},
    "status": {
        "queued": {"ar": "⏳ في الطابور", "en": "⏳ queued"},
        "generating": {"ar": "🎬 قيد التجهيز", "en": "🎬 generating"},
        "review": {"ar": "👀 بانتظار رأيك", "en": "👀 waiting for your review"},
        "awaiting_payment": {"ar": "💳 بانتظار الدفع", "en": "💳 awaiting payment"},
        "done": {"ar": "✅ مكتمل", "en": "✅ done"},
        "cancelled": {"ar": "❌ ملغي", "en": "❌ cancelled"},
        "failed": {"ar": "⚠️ متعثر", "en": "⚠️ failed"},
    },
    "lang_name": {"ar": {"ar": "العربية", "en": "الإنجليزية"}, "en": {"ar": "Arabic", "en": "English"}},
}


def t(lang, key, **kw):
    lang = lang if lang in ("ar", "en") else "ar"
    val = TEXTS[key][lang]
    return val.format(**kw) if kw else val


def status_label(lang, status):
    lang = lang if lang in ("ar", "en") else "ar"
    return TEXTS["status"].get(status, {}).get(lang, status)
