<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../assets/logo-dark.svg">
    <img src="../../assets/logo.svg" width="360" alt="voxar"/>
  </picture>
</p>

<p align="center">
  <b>صوت يفهم اللهجات ويعمل على جهازك أنت.</b><br>
  تحويل الكلام إلى نص بشكل متدفّق، وتحويل النص إلى كلام باللهجة السعودية: بلا سحابة، وبلا تتبّع، وبأمر واحد.
</p>

<div align="center">

🇺🇸 <a href="../../README.md">English</a> | 🇸🇦 <a href="README.ar-SA.md">العربية</a>

</div>

<p align="center">
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue" alt="License: Apache-2.0"/></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/status-pre--alpha-orange" alt="Status: pre-alpha"/>
</p>

<div dir="rtl">

> **مرحلة ما قبل ألفا.** السرعة والذاكرة وحِمل الخادم قيست على جهاز واحد: انظر [الأداء](#الأداء-مقيس-على-جهاز-واحد).

شغّل `voxar transcribe` على ملف صوتي فيتحول الكلام العربي إلى نص على جهازك. شغّل `voxar say` فيتحول النص باللهجة السعودية إلى كلام. ووجّه وكيل ذكاء اصطناعي إلى `voxar mcp` ليستخدم الاثنين.

- **على الجهاز وخاص بك.** النماذج تعمل محليًا. لا يُرسل أي صوت إلى أي مكان، ولا يوجد تتبّع. الاستخدام الوحيد للشبكة هو تنزيل النموذج صراحةً عبر `voxar models pull`.
- **كل نموذج يُتحقَّق منه.** التنزيل عبر HTTPS فقط، وكل ملف يُقارَن ببصمة SHA-256 مثبّتة قبل استخدامه. التنزيل التالف أو المقطوع لا يظهر أبدًا كأنه مثبَّت.
- **نواة صغيرة بلا اعتماديات.** نواة voxar بترخيص Apache-2.0 ولا تحتاج إلى أي اعتمادية وقت التشغيل. المحرّكات وخادم MCP وخادم HTTP إضافات اختيارية، وتحويل النص إلى كلام حزمة منفصلة بترخيص GPL-3.0 عن قصد (انظر [الترخيص](#الترخيص)).

**ابدأ** (دقيقة تقريبًا، إضافة إلى تنزيل نموذج بحجم ~31 ميغابايت):

</div>

```bash
git clone https://github.com/HasanBGit/Voxar.git
cd Voxar
make setup     # install
make models    # download the speech-to-text model
make run       # then open http://127.0.0.1:8765
```

<div dir="rtl">

تحتاج إلى [Python 3.10+](https://www.python.org/downloads/) و[uv](https://docs.astral.sh/uv/). لا تملك `make` (مثلًا على ويندوز)؟ شغّل أوامر ملف [`Makefile`](../../Makefile) يدويًا: `uv sync --extra moonshine --extra mcp --extra server` ثم `uv run voxar models pull moonshine-tiny-streaming-ar --accept-license`.

أو انسخ ملفًا صوتيًا من سطر الأوامر، بملف WAV بتردد 16 كيلوهرتز، قناة واحدة، 16 بت:

</div>

```bash
uv run voxar transcribe sample.wav
```

<div dir="rtl">

هذا كل شيء. يُحفظ النموذج في ذاكرة التخزين المؤقتة بعد التحقق منه:

</div>

```
~/.cache/voxar/
└── moonshine-tiny-streaming-ar/
    └── quantized_26_08_24/     8 files, each matching its pinned SHA-256
```

<div dir="rtl">

**يعمل مع** أي عميل [MCP](https://modelcontextprotocol.io) عبر `voxar mcp` (جُرّب هنا بعميل MCP الرسمي لمكتبة بايثون، وليس بمنتجات محدّدة)، ومع أي تطبيق عبر الخادم المحلي.

---

## مثال حقيقي

مخرجات حقيقية من هذا المستودع. الصوت صوت عربي اصطناعي مولَّد بأمر `say` في macOS، وليس تسجيلًا لإنسان:

</div>

```text
$ voxar doctor
voxar: 0.0.1
python: 3.10.20 (Darwin)
cache dir: ~/.cache/voxar (exists: True)
offline: False
recognizers: moonshine
synthesizers: nabra-saudi

$ voxar transcribe sample.wav
السلام عليكم ورحمة الله وبركاته كيف نحالك اليوم
```

<div dir="rtl">

الجملة المرجعية كانت «السلام عليكم ورحمة الله وبركاته. كيف حالك اليوم؟»: كلمة واحدة خاطئة («نحالك» بدل «حالك»). عيّنة اصطناعية واحدة نظيفة تُثبت أن المسار يعمل، ولا تقول شيئًا عن الدقة على الكلام الحقيقي أو باللهجة السعودية.

رحلة ذهاب وإياب عبر المحرّكين (تحويل نص سعودي إلى كلام، ثم تحويل المخرَج إلى نص):

</div>

```text
$ VOXAR_SYNTHESIZER=nabra-saudi voxar say "يا أهلاً وسهلاً، كيف حالكم؟ إن شاء الله طيبين وبأحسن حال." -o hello.wav
$ ffmpeg -i hello.wav -ar 16000 -ac 1 -sample_fmt s16 hello16k.wav
$ voxar transcribe hello16k.wav
يا أهلا وسهلا كيف حالكم إن شاء الله طيبين وبأحسن حال
```

<div dir="rtl">

---

## ماذا يفعل

| الإمكانية | ما تحصل عليه |
|---|---|
| **تحويل ملف صوتي إلى نص** | `voxar transcribe` يعيد النص النهائي (Moonshine العربي المتدفّق) |
| **نص إلى كلام باللهجة السعودية** | `voxar say` يكتب ملف WAV بتردد 24 كيلوهرتز بصوت أنثوي واحد، عبر إضافة اختيارية بترخيص **GPL-3.0** تحتاج إلى torch |
| **خادم MCP للوكلاء** | `transcribe_file` و`speak` و`list_engines` عبر stdio، مع حصر الوصول إلى الملفات في مجلدات مسموح بها |
| **خادم HTTP/WebSocket محلي** | `POST /v1/transcribe` و`POST /v1/speak` و`WS /v1/stream` للبث الحي |
| **تنزيل نماذج موثَّق** | `voxar models pull/verify`: HTTPS فقط، وبصمة SHA-256 مثبّتة، وتثبيت ذرّي |

---

## أمثلة

ثمانية سكربتات قابلة للتشغيل في [`examples/`](../../examples/README.md)، جُرّب كل منها على النماذج الحقيقية: واجهة بايثون، والبث بنمط الوقت الحقيقي، وتحويل النص إلى كلام، وعميل HTTP ينتظر ويعيد المحاولة عند `503`، وعميل WebSocket، وعميل MCP، ونسخ مجلد كامل دفعة واحدة، ورحلة «قول ثم نسخ».

</div>

```bash
uv run python examples/01_transcribe_file.py sample.wav
uv run python examples/02_stream_from_wav.py sample.wav
uv run python examples/07_batch_transcribe.py recordings/ transcripts.jsonl
```

<div dir="rtl">

مخرجات حقيقية (صوت عربي اصطناعي):

</div>

```text
$ uv run python examples/02_stream_from_wav.py greeting.wav
partial السلام عليكم
partial السلام علي
partial السلام عليكم ورحمة الله
partial السلام عليكم ورحمة الله وبركاته
final   السلام عليكم ورحمة الله وبركاته
```

<div dir="rtl">

النص الجزئي (`partial`) قد يتغيّر (لاحظ تعديل «السلام علي»)، أما السطر النهائي (`final`) فلا يتغيّر أبدًا.

---

## الأداء (مقيس على جهاز واحد)

جهاز Apple M4 محمول، 10 أنوية، 16 غيغابايت، معالج فقط (بلا GPU). أرقامك ستختلف؛ المنهجية والسكربتات لإعادة القياس في [docs/performance.md](../performance.md).

| ما المقيس | النتيجة |
|---|---|
| سرعة الكلام إلى نص | نحو **18 ضعف الزمن الحقيقي** على مقاطع من 3 إلى 6 ثوانٍ (RTF وسيط 0.054)، و**من 23 إلى 32 ضعفًا** على صوت من 38 إلى 115 ثانية |
| البدء | يُحمَّل النموذج في نحو 0.3 ثانية؛ أمر `voxar transcribe` لمقطع 4 ثوانٍ يستغرق 0.28 ثانية كعملية كاملة |
| سرعة النص إلى كلام | نحو **30 ضعف الزمن الحقيقي** (RTF 0.033)؛ وبدء بارد 4.0 ثوانٍ |
| الذاكرة | نحو 300 إلى 340 ميغابايت للكلام إلى نص، ونحو 560 ميغابايت ذروةً للنص إلى كلام |
| إنتاجية الخادم | نحو **7 طلبات/ثانية** لمقاطع 4 ثوانٍ (28 ثانية صوت في كل ثانية)، ثابتة من عميل إلى 8 عملاء؛ ومع 8 عملاء يبلغ زمن الاستجابة p95 نحو 1.6 ثانية |
| الحِمل الزائد | بعد 9 طلبات في الطابور يردّ الخادم فورًا بـ `503` بدل إبطاء الجميع |
| البث الحي | أول نص بعد نحو ثانية من بدء الكلام؛ والنص النهائي خلال 0.2 ثانية من النهاية؛ و4 تدفقات معًا |
| الدقة (صوت اصطناعي فقط) | 8 جمل بالفصحى: WER 4.1٪ وCER 0.7٪. و4 جمل بصياغة لهجية يقرؤها صوت فصيح: WER 29٪ وCER 5٪ |

</div>

```bash
uv run python scripts/benchmark.py asr clips/*.wav --refs refs.json --repeat 3   # speed, memory, WER/CER
uv run python scripts/loadtest.py http --file clip.wav --concurrency 8 --requests 32   # with `voxar serve` running
```

<div dir="rtl">

---

## التثبيت

ثبّت voxar من مجلد المشروع. النواة بلا اعتماديات، والمحرّكات والخوادم إضافات اختيارية:

</div>

```bash
uv sync                                  # core only
uv sync --extra moonshine                # + Arabic speech-to-text engine
uv sync --extra moonshine --extra mcp --extra server   # + MCP server and local HTTP server
```

<div dir="rtl">

**تحويل النص إلى كلام حزمة منفصلة** بترخيص مختلف (GPL-3.0). تحتاج إلى torch وtransformers (بيئة بحجم 900 ميغابايت تقريبًا):

</div>

```bash
uv pip install -e plugins/voxar-tts-espeak
uv run voxar models pull nabra-saudi-7m --accept-license      # ~31 MB
VOXAR_SYNTHESIZER=nabra-saudi uv run voxar say "السلام عليكم" -o hello.wav
```

<div dir="rtl">

اكتب النص باللهجة كما يكتبها الناس، **بدون تشكيل كامل** (التشكيل يُضعف هذا النموذج). الكلمات اللاتينية تُحذف، والنص الذي لا يحوي ما يُنطق يُعدّ خطأ.

---

## الاستخدام من التطبيقات والوكلاء

وكيل عبر MCP:

</div>

```bash
uv sync --extra moonshine --extra mcp
uv run voxar mcp --allow-dir ./audio
```

<div dir="rtl">

الوكيل يتحكم في كل وسيط، لذلك يجب أن تقع مسارات الملفات **داخل مجلد مسموح به** (الافتراضي: مجلد العمل، ولا يمكن الهروب منه بـ `..` أو الروابط الرمزية)، وأداة `speak` لا تستبدل ملفًا موجودًا إلا مع `overwrite=true`، ولا يُقرأ إلا صوت WAV.

خادم محلي للتطبيقات:

</div>

```bash
uv sync --extra moonshine --extra server
uv run voxar serve                      # http://127.0.0.1:8765
```

<div dir="rtl">

> **لا تعرّض هذا الخادم لشبكة لا تثق بها.** ليس فيه مصادقة ولا HTTPS. وهو يرفض أي عنوان غير `127.0.0.1` ما لم تمرّر `--allow-remote`.

**صفحة اختبار في المتصفح:** يقدّم `voxar serve` صفحة اختبار صغيرة على عنوانه نفسه. افتح **http://127.0.0.1:8765** لترفع ملفًا صوتيًا فترى النص، أو لتكتب نصًا فتسمعه بالصوت السعودي. كل شيء يعمل على جهازك. وفيها لوحتان: **Listen** (أسقِط ملفًا صوتيًا فيُنسخ في ثوانٍ، أو فعّل «Play the file as live» ليُبَثّ بسرعة الكلام فيظهر النص أثناء التشغيل: الرمادي ما زال يتغيّر والأسود نهائي) و**Speak** (اكتب نصًا أو اضغط إحدى ثلاث جمل جاهزة).

---

## الخصوصية

- **لا تتبّع** ولا تحليلات ولا اتصال بجهات خارجية.
- **الصوت لا يغادر جهازك.** التعرّف والتوليد يعملان محليًا. تُستخدم الشبكة في `voxar models pull` الذي ينزّل ملفات النموذج عبر HTTPS من ناشره ويتحقق منها، وفي `voxar llm` الذي يرسل **النص الذي تعطيه إياه فقط** إلى المزوّد الذي تختاره. المزوّدون المحليون (`ollama` و`lmstudio`) يُبقون حتى هذا النص على جهازك.
- اضبط `VOXAR_OFFLINE=1` لمنع أي تنزيل ولحجب مزوّدي النماذج اللغوية البعيدين.
- قد يحتوي الصوت على بيانات شخصية، فلا ترفق تسجيلات في بلاغات الأخطاء.

---

## الترخيص

شيفرة voxar نفسها بترخيص **Apache-2.0**. وكل نموذج واعتمادية من طرف ثالث يحتفظ بترخيصه الخاص، وهي مدرجة مع تواريخ الفحص في [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md)، ونصوصها في [LICENSES](../../LICENSES/)، وإشعارات النسب في [NOTICE](../../NOTICE).

اقرأ هذا قبل أي استخدام تجاري:

1. **ترخيص نموذج Moonshine العربي غير مؤكَّد.** مستودعه الأصلي يقول MIT، لكن أداة التنزيل لديهم تطبع إشعارًا عامًّا بأنه غير تجاري لكل لغة غير الإنجليزية. احصل على تأكيد كتابي من Moonshine AI.
2. **إضافة تحويل النص إلى كلام بترخيص GPL-3.0** لأن بيئة تشغيلها تضم `espeak-ng`. وهي حزمة منفصلة لا تستوردها النواة أبدًا ([ADR 0002](../adr/0002-license-split.md)). هذا ليس استشارة قانونية.
3. **موافقة صاحب الصوت السعودي غير موثَّقة** في المصدر الأصلي.
4. عدة مجموعات بيانات للكلام السعودي غير تجارية أو تشترط المشاركة بالمثل. راجع [DATA.md](../../DATA.md) قبل تدريب أي شيء.

---

## المساهمة

المساهمات مرحَّب بها. راجع [CONTRIBUTING.md](../../CONTRIBUTING.md) للإعداد والقواعد (تتبّع التراخيص، وألّا تُذكر إلا ادعاءات مدعومة بقياس، واختبار لكل تغيير)، و[SUPPORT.md](../../SUPPORT.md) لبلاغات الأخطاء. المسائل الأمنية: [SECURITY.md](../../SECURITY.md).

للتفاصيل الكاملة، وجداول المتغيرات البيئية، واستكشاف الأخطاء، ومرجع الأوامر، انظر [README بالإنجليزية](../../README.md).

</div>
