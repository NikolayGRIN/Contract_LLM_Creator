# src/prompts/topic_checklists.py
# One dictionary: key = section_id (as used in your pipeline)

SECTION_CHECKLISTS = {
    # ---------------------------------------------------------
    # FORM-BASED SECTIONS
    # ---------------------------------------------------------
    "definitions": {
        "ru": """
=== TOPIC CHECKLIST (ОПРЕДЕЛЕНИЯ) ===
Сформируй определения, каждое — отдельный подпункт. Покрой РАЗНЫЕ термины, без повторов и перефразов:
- Стороны: “Поставщик”, “Покупатель”, общий термин “Сторона/Стороны” (если упоминаются).
- Договор/Контракт, дата заключения, дата вступления в силу, срок действия (как понятия).
- Товары/Оборудование/Продукция, комплектность, принадлежности, ЗИП/расходники (если применимо).
- Спецификация/Приложение/Техническое задание, “Неотъемлемая часть договора”.
- Партия/частичная отгрузка/поставка, отгрузочные документы.
- Цена договора/стоимость, валюта, база цены (за единицу/за партию/фикс).
- НДС/VAT как режим (без ставок), пошлины/сборы (как понятие).
- Счет/Инвойс, счет-фактура (если применимо), дата счета, дата оплаты (как понятия).
- Платеж/банковский перевод, банковские комиссии (как понятие).
- Поставка/доставка/перевозка, срок поставки, место поставки, переход рисков, переход права собственности (как понятия).
- Инкотермс (если используется), “DAP/EXW/etc” как понятия (без детализации).
- Приемка/инспекция, документ приемки (акт/сертификат/протокол), срок приемки.
- Дефект/несоответствие/замечания, уведомление о недостатках (как понятие).
- Гарантия, гарантийный срок, начало гарантии, способ устранения (ремонт/замена).
- Форс-мажор, уведомление, подтверждающие документы (как понятия).
- Спор/претензия/требование, компетентный суд/арбитраж (как понятия).
- Конфиденциальная информация, персональные данные (если упоминаются).
Требование: 10–15 определений; каждое определение — самостоятельное.
""",
        "en": """
=== TOPIC CHECKLIST (DEFINITIONS) ===
Define distinct terms, one per subclause, avoiding near-duplicates:
- Parties: “Supplier”, “Buyer”, “Party/Parties”, “Affiliates” (if used).
- Contract/Agreement, execution date, effective date, term (as concepts, no dates).
- Goods/Equipment/Products, completeness, accessories, spare parts/consumables (if applicable).
- Specification/Annex/Technical Assignment, “Integral part of the Contract”.
- Batch/Partial Shipment/Delivery, shipping documents.
- Contract Price/Price, Currency, price basis (per unit/per lot/lump sum).
- VAT as a mode (no rates), duties/fees (as concepts).
- Invoice, invoice date, payment date (as concepts), tax invoice (if applicable).
- Payment / bank transfer, bank charges (as concepts).
- Delivery/dispatch/transportation, delivery time, delivery place, transfer of risk, transfer of title (as concepts).
- Incoterms (if used) and terms like DAP/EXW (as concepts).
- Acceptance/inspection, acceptance document (act/certificate/protocol), acceptance period.
- Defect/non-conformity/remarks, defect notice (as a concept).
- Warranty/warranty case, warranty period, warranty start, remedy (repair/replacement).
- Force Majeure, notice, evidence (as concepts).
- Dispute/claim/demand, competent court/arbitration (as concepts).
- Confidential Information (if used), personal data (if used).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
At least 10–15 definitions; avoid “as defined in section…”.
"""
    },

    "subject_of_contract": {
        "ru": """
=== TOPIC CHECKLIST (ПРЕДМЕТ ДОГОВОРА) ===
Покрой РАЗНЫЕ аспекты предмета (не уходи в оплату/ответственность/форс-мажор):
- Обязательство Поставщика поставить Товары/Оборудование по Спецификации/Приложению.
- Обязательство Покупателя принять Товары и оформить приемку документально.
- Количество/комплектность: “согласно Спецификации”, без цифр (если не задано).
- Требование “новые, не бывшие в употреблении” (общо).
- Требования к качеству: соответствие стандартам/сертификатам (общо).
- Документация: паспорта, инструкции, сертификаты (общо).
- Место и способ передачи товара (общо).
- Переход права собственности (общо).
- Переход рисков и момент/условие перехода.
- Частичные поставки/партии (если допускаются) — общо.
- Сопутствующие материалы/ЗИП/расходники (если применимо).
- Указание, что Спецификация/Приложения — неотъемлемая часть договора.
Сделай 12–17 подпунктов; каждый — новая тема, без перефразов.
""",
        "en": """
=== TOPIC CHECKLIST (SUBJECT OF CONTRACT) ===
Cover distinct subject aspects (do not drift into payment/liability/force majeure):
- Supplier’s obligation to deliver Goods/Equipment per Specification/Annex.
- Buyer’s obligation to accept Goods and document acceptance.
- Quantity/assortment/completeness: “as per Specification” (no extra numbers if not provided).
- New goods only (not used/refurbished).
- Quality compliance: Specification and standards/certificates (generic).
- Documentation: manuals, passports, certificates, warranty documents (generic).
- Place/method of delivery/hand-over and linkage to acceptance.
- Transfer of title and trigger event.
- Transfer of risk and trigger event/condition.
- Partial shipments/batches (if allowed).
- Optional spare parts/consumables/accessories (if applicable).
- Substitution/equivalents only by mutual agreement (generic).
- Specification/Annex as integral part of Contract.
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 12–17 subclauses; each is a new topic.
"""
    },

    "price_and_taxes": {
        "ru": """
=== TOPIC CHECKLIST (ЦЕНА И НАЛОГИ) ===
Не уходи в сроки/порядок оплаты. Раскрой цену и налоги разными темами:
- Валюта цены и валюта договора (как в форме).
- Общая цена договора.
- База цены (фикс/за единицу/за партию/за этап).
- Структура цены: “включает/не включает” упаковку (по форме), общо про маркировку/тару.
- НДС/VAT режим по форме: включен/начисляется сверх/не применяется — без ставок и цифр.
- Налоги/пошлины/сборы “если применимо”.
- Подтверждающий документ цены: Спецификация/Приложение/инвойсы (общо).
- Распределение цены по партиям/этапам/позициям Спецификации (общо, если применимо).
- Порядок изменения цены: только письменное соглашение/доп. соглашение (общо).
- Запрет одностороннего изменения цены (общо).
- Изменение обязательных налогов/пошлин (общо).
- Условие о том, что цена включает обычные расходы Поставщика (общо).
- Запрет скрытых платежей/двойного начисления/необоснованных сборов (общо). 
- Налоговые документы: счет-фактура/инвойс (если применимо) — общо.
Сделай 10–15 подпунктов; каждый — новая тема (не повторять “Цена не изменяется…”).
""",
        "en": """
=== TOPIC CHECKLIST (PRICE AND TAXES) ===
Do not drift into payment timing. Cover price/tax topics distinctly:
- Currency of price and contract currency (from form).
- Total contract price (from form).
- Price basis (lump sum/per unit/per lot/per milestone).
- Price composition: includes/does not include marking/packing.
- If VAT is added: “if applicable under law”, no percentages.
- Taxes/duties/fees allocation “if applicable”, no specifics.
- Price evidence: Specification/Annex/invoices (generic).
- Allocation across batches/milestones/specification items (generic if applicable).
- Price changes only by written agreement (generic).
- No unilateral price change (generic).
- Changes in mandatory taxes/duties: handled as per law and/or agreement (generic, careful).
- Price includes customary supplier costs (generic, not “everything”).
- No hidden fees / no double charging (generic).
- Documentation of adjustments: amendment/specification/corrective document (generic).
- Tax documents: invoice/tax invoice where applicable (generic).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 10–15 subclauses; each must add a NEW topic (avoid using “price shall not change” repeatedly).
"""
    },

    "acceptance_and_inspection": {
        "ru": """
=== TOPIC CHECKLIST (ПРИЕМКА И ИНСПЕКЦИЯ) ===
Покрой приемку разными аспектами (не уходи в гарантию/штрафы/оплату):
- Обязанность Покупателя провести приемку и осмотр Товаров.
- Срок приемки: по форме или общо; как считается начало срока (доставка/передача/документы).
- Место приемки (общо) и кто обеспечивает доступ/условия осмотра (общо).
- Документ приемки: акт/протокол/сертификат (как в форме) и его юридическое значение.
- Перечень отгрузочных документов (накладная/упаковочный лист/сертификаты) — общо.
- Приемка по количеству отдельно от приемки по качеству.
- Осмотр упаковки и фиксация повреждений при приемке.
- Порядок фиксации замечаний в акте/протоколе (общо).
- Уведомление о несоответствиях: форма/канал/срок “в разумный срок/в течение срока приемки” (общо).
- Условия “deemed acceptance” (молчаливое принятие) — аккуратно, общо.
- Приемка при частичных поставках: пропорционально партии, отдельные акты (общо).
- Право инспекции/представителя/третьей стороны (общо) и обязанность содействовать.
- Отбор проб/испытания (если применимо) — общо, без методик.
- Разграничение “видимые” и “скрытые” недостатки (общо).
- Хранение документов приемки и предоставление копий (общо).
- Неопределенность/спор по приемке: порядок согласования/совместного осмотра (общо).
Сделай 14–18 подпунктов; каждый — новая тема, без перефразов.
""",
        "en": """
=== TOPIC CHECKLIST (ACCEPTANCE AND INSPECTION) ===
Cover acceptance distinctly (no warranties/penalties/payment):
- Buyer’s duty to inspect and accept the Goods.
- Acceptance period: per form or generic; how the period starts (delivery/hand-over/documents).
- Place of acceptance (generic) and access/conditions for inspection (generic).
- Acceptance document: act/protocol/certificate (per form) and its legal effect.
- Shipping documents (delivery note/packing list/certificates) (generic).
- Acceptance by quantity separate from acceptance by quality.
- Packaging inspection and recording transit damage.
- How discrepancies are recorded in the acceptance document (generic).
- Notice of non-conformities: form/channel/time “within acceptance period/reasonable time” (generic).
- Deemed acceptance concept (generic, careful).
- Acceptance for partial shipments: separate acts per batch (generic).
- Inspection rights/representatives/third-party inspection (generic) and cooperation duty.
- Sampling/tests (if applicable) (generic, no methods).
- Visible vs latent defects distinction (generic).
- Storage/retention of acceptance documents and copies (generic).
- Disputes on acceptance: joint inspection / reconciliation (generic).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 14–18 subclauses; each is a NEW topic.
"""
    },

    "warranties": {
        "ru": """
=== TOPIC CHECKLIST (ГАРАНТИИ) ===
Раскрой гарантию без штрафов/пеней и без повторов:
- Гарантийный срок по форме или общо, начало гарантии (с приемки/поставки/ввода в эксплуатацию — по форме или общо).
- Что считается гарантийным случаем: дефект/несоответствие Спецификации (общо).
- Исключения: неправильная эксплуатация, вмешательство, расходные материалы, форс-мажорные повреждения (общо).
- Обязанность Покупателя уведомить о дефекте (общо) и минимальное содержание уведомления (общо).
- Срок реакции/осмотра/подтверждения (по форме или общо).
- Способ устранения: ремонт/замена/ремонт или замена (по форме), выбор стороны (общо).
- Доступ к товару/условия проведения ремонта, обязанность содействия (общо).
- Порядок возврата/передачи дефектного товара (общо).
- Расходы на доставку/логистику по гарантии: “по соглашению/если применимо” (без цифр).
- Гарантия на замененные/отремонтированные части и продление срока (общо, без сроков).
- Документы по гарантийному обслуживанию: акт/заключение/акт замены (общо).
- Ограничения: гарантия не является страхованием, не покрывает косвенные убытки (если не противоречит форме) — общо.
- Сохранение серийных номеров/пломб (общо, если применимо).
- Обязанность соблюдать инструкции производителя (общо).
- Условия отказа в гарантии при нарушении правил эксплуатации (общо).
Сделай 14–18 подпункта; каждый — новая тема, избегай повторяющихся конструкций “Покупатель обязан…”.
""",
        "en": """
=== TOPIC CHECKLIST (WARRANTIES) ===
Expand warranty without penalties and avoid near-duplicates:
- Warranty period per form or generic; warranty start trigger (acceptance/delivery/commissioning per form/generic).
- What is a warranty case: defects/non-conformance to Specification (generic).
- Exclusions: misuse, unauthorized repair, consumables, damage due to force majeure (generic).
- Buyer’s duty to notify defects (generic) and minimum notice content (generic).
- Response/inspection/confirmation time (per form or generic).
- Remedy: repair/replacement/repair or replacement (per form), selection mechanism (generic).
- Access to goods and cooperation during repair (generic).
- Return/hand-over procedure for defective goods (generic).
- Logistics/costs for warranty service: “as agreed/if applicable” (no numbers).
- Warranty on replaced/repaired parts and extension (generic, no durations).
- Warranty service documentation: report/act/replacement act (generic).
- Limitations: not insurance; no indirect losses if consistent with form (generic).
- Serial numbers/seals preservation (generic if applicable).
- Duty to follow manufacturer instructions (generic).
- Warranty refusal conditions upon misuse (generic).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 14–18 subclauses; each must add a NEW topic.
"""
    },

    "liability_and_penalties": {
        "ru": """
=== TOPIC CHECKLIST (ОТВЕТСТВЕННОСТЬ И ШТРАФЫ) ===
Пиши развернуто, строго по форме, без придуманных ставок/процентов. Каждая строка — отдельная тема:
- Общий принцип ответственности за нарушение обязательств (общо).
- Основание ответственности: вина/причинная связь/убытки (общо, без доктрины).
- Лимит ответственности: включен/не включен; тип (aggregate/per event) и объем — строго по форме.
- Исключение косвенных убытков/упущенной выгоды/потери данных — по форме (или общо, если флаг).
- Исключения из лимита: fraud/wilful misconduct и др. — по форме.
- Ответственность за нарушение конфиденциальности/персональных данных (если есть в форме) — общо.
- Ответственность за качество/комплектность/документы (общо).
- Просрочка поставки: если штрафы отключены — без ставок (“может быть взыскана в порядке…/по закону”).
- Просрочка оплаты: если секция liability это допускает и если предусмотрено формой — общо, без ставок (иначе не трогай).
- Нарушение гарантийных обязательств: меры (ремонт/замена) без штрафных ставок.
- Уведомление о претензии/срок предъявления претензий (если в форме) — общо.
- Обязанность минимизировать убытки (общо).
- Качество доказательств убытков/документация (общо).
- Кумуляция средств защиты/исключительность лимита (общо).
- Солидарность/раздельность ответственности (если применимо) — общо.
- Форс-мажор как основание освобождения (общо, ссылка).
- Порядок зачета/удержаний — не описывать, если это Payment Terms; только общая запретительная формулировка при необходимости.
- Сохранение иных средств защиты, кроме штрафов (общо).
Сделай 14–18 подпунктов; избегай серии строк “Ответственность за …” — вариируй начальные конструкции.
""",
        "en": """
=== TOPIC CHECKLIST (LIABILITY AND PENALTIES) ===
Be detailed, respect the form flags; do NOT invent rates/percentages. Each line must introduce a NEW topic:
- General liability principle (generic).
- Elements: fault/causation/damages (generic, concise).
- Liability cap: enabled/disabled; type (aggregate/per event) and scope strictly per form.
- Exclusion of indirect damages / loss of profit / data loss per form (or generic if flagged).
- Exceptions to cap: fraud/wilful misconduct etc. per form.
- Liability for confidentiality/personal data breach (if applicable) (generic).
- Liability for quality/completeness/documents (generic).
- Delay in delivery: if penalties disabled, describe generically (no rates).
- Late payment: only if supported by form/section policy; otherwise omit (no rates).
- Warranty breach: remedies (repair/replace) without penalty rates.
- Claim notice period if provided (generic wording).
- Duty to mitigate losses (generic).
- Evidence/documentation of damages (generic).
- Cumulation/exclusivity of remedies/caps (generic).
- Joint/several liability (if applicable) (generic).
- Force majeure relief reference (generic).
- Set-off/withholding: avoid payment detail; only generic prohibition if needed.
- Preservation of other remedies beyond penalties (generic).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 14–18 subclauses; vary sentence starters (avoid repeating “Liability for…”).
"""
    },

    "force_majeure": {
        "ru": """
=== TOPIC CHECKLIST (ФОРС-МАЖОР) ===
Каждый подпункт — законченное предложение, без пустых строк “Уведомление”. Избегай повторов одной формулы.
Покрой разные темы:
- Определение форс-мажора и критерии (непредотвратимость/непредвиденность) — общо.
- Примеры событий (стихии, война, запреты властей, эпидемии, сбои инфраструктуры) — без исчерпывающего списка.
- Обязанность своевременно уведомить другую сторону; форма уведомления (письменно/электронно) — общо.
- Содержание уведомления: событие, влияние, предполагаемый срок, меры по минимизации — общо.
- Подтверждающие документы/сертификаты (если применимо) — общо.
- Приостановление исполнения обязательств на период форс-мажора (общо).
- Продление сроков исполнения на период форс-мажора (общо).
- Частичное исполнение, если возможно, и обязанность сотрудничества (общо).
- Обязанность минимизировать последствия и возобновить исполнение при прекращении (общо).
- Порядок уведомления о прекращении форс-мажора (общо).
- Право на расторжение при длительном форс-мажоре (общо; без конкретных дней, если не задано).
- Отсутствие ответственности/штрафов на период форс-мажора (общо).
- Исключения: денежные обязательства/оплата обычно не освобождаются (аккуратно, общо).
- Запрет злоупотребления форс-мажором; обязанность доказать причинную связь (общо).
- Разделение рисков/расходов при форс-мажоре (общо, без цифр).
Сделай 12–16 подпункта; избегай повторов “В случае возникновения… стороны обязаны принять меры…” много раз.
""",
        "en": """
=== TOPIC CHECKLIST (FORCE MAJEURE) ===
Each subclause must be a complete sentence; no empty “Notice” lines. Avoid repeating the same template.
Cover distinct topics:
- Definition and criteria (beyond control / unforeseeable / unavoidable) (generic).
- Illustrative events (natural disasters, war, government restrictions, epidemics, infrastructure failures) (non-exhaustive).
- Timely notice duty; notice form (written/electronic) (generic).
- Notice content: event, impact, expected duration, mitigation steps (generic).
- Evidence/certificates (where applicable) (generic).
- Suspension of performance during FM (generic).
- Extension of time for performance (generic).
- Partial performance if feasible and cooperation duty (generic).
- Duty to mitigate and resume performance upon cessation (generic).
- Notice of cessation (generic).
- Termination right for prolonged FM (generic; no durations if not provided).
- No liability/penalties during FM (generic).
- Carve-outs: payment obligations typically not excused (careful, generic).
- No abuse; duty to prove causation (generic).
- Allocation of costs/risks during FM (generic, no numbers).
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 12–16 subclauses; avoid repeating “In case of FM the Parties shall…” many times.
"""
    },

    "governing_law_and_disputes": {
        "ru": """
=== TOPIC CHECKLIST (ПРИМЕНИМОЕ ПРАВО И СПОРЫ) ===
Юридически аккуратно, без “воды” и без повторов “суды компетентны”. Каждая строка — новая тема:
- Применимое право (строго по форме: страна/право).
- Компетентный суд/подсудность/место рассмотрения (строго по форме).
- Досудебный порядок: переговоры и/или претензия (если не задано — общо).
- Срок рассмотрения претензии: только общо (“в разумный срок”), если конкретика не задана.
- Форма и способ направления претензий/уведомлений по спору (общо, без реквизитов).
- Язык переписки и документов по спору (общо или по форме).
- Применимые правила доказывания/документы (общо, без ссылок на статьи кодекса).
- Обеспечительные меры (право обратиться за ними) — общо.
- Судебные расходы/госпошлина/расходы на представителей — общо.
- Исполнимость отдельных положений — общо.
- Сохранение действия отдельных обязательств после прекращения договора  — общо.
- Запрет самоуправства/обязанность действовать добросовестно при урегулировании (общо).
- Никаких конкретных сроков исковой давности; можно указать “по применимому праву”.
- Пиши полные и развернутые предложения.
Сделай 14–20 подпунктов; убери повторы и не перечисляй одно и то же разными словами.
""",
        "en": """
=== TOPIC CHECKLIST (GOVERNING LAW AND DISPUTES) ===
Be precise and avoid repetitive filler (“courts are competent…”). Each line must be a NEW topic:
- Governing law (strictly per form: jurisdiction/law).
- Competent court / venue / jurisdiction (strictly per form).
- Pre-dispute step: negotiation and/or claim (generic if not provided).
- Claim review time: generic (“within a reasonable time”) if not specified.
- Form/method of dispute notices/claims (generic; no bank details).
- Language of dispute communications/documents (generic or per form).
- Evidence/document handling (generic; no statutory citations).
- Injunctive/interim relief availability (generic).
- Allocation of legal costs/fees/expenses (generic).
- Severability concept (generic).
- Survival of certain obligations after termination/expiry (generic).
- Good faith / no self-help framing for dispute resolution (generic).
- No specific limitation periods; state “as per applicable law”.
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 14–20 subclauses; avoid rephrasing the same idea multiple times.
"""
    },

    # ---------------------------------------------------------
    # RETRIEVAL SECTIONS (LLM still generates final text)
    # ---------------------------------------------------------
    "payment_terms": {
        "ru": """
=== TOPIC CHECKLIST (УСЛОВИЯ ОПЛАТЫ) ===
Каждый подпункт должен раскрывать НОВЫЙ аспект условий оплаты. НЕЛЬЗЯ повторять/перефразировать одну и ту же тему.
Покрой разные аспекты, например:
- основание для оплаты (счет/инвойс/акт)
- срок оплаты и порядок исчисления дней
- размер предоплаты (авансового платежа) в процентах
- момент исполнения обязательства по оплате
- валюта платежа
- банковские комиссии
- порядок выставления счетов/инвойсов
- подтверждающие документы (поставка/приемка)
- частичная/поэтапная оплата (если применимо)
- корректировочные счета/кредит-ноты
- оспаривание сумм (только механика оплаты неоспариваемой части)
- запрет/условия удержаний и зачетов (withholding/set-off)
- возврат переплаты / зачет переплаты
- сверка взаиморасчетов
- подтверждение платежей / хранение документов
- электронный документооборот по счетам
Требование: 20–30 подпунктов; 1 подпункт = 1 новая тема; без дублей.
Начинай подпункты разными фразами. 
""",
        "en": """
=== TOPIC CHECKLIST (PAYMENT TERMS) ===
Each subclause must cover a NEW aspect of payment mechanics. Do NOT repeat or paraphrase the same topic.
Cover distinct topics such as:
- basis for payment (invoice/act)
- payment term and day-count rule
- volume of prepayment (advance payment) in percentage
- moment of payment completion
- payment currency
- bank charges
- invoicing procedure
- supporting documents (delivery/acceptance)
- partial/milestone payments (if applicable)
- corrective invoices / credit notes
- disputed amounts (payment of undisputed part only; no disputes section)
- withholding/set-off rules
- overpayment refund/set-off
- reconciliation
- confirmations / record keeping
- e-invoicing / electronic documents
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 20–30 subclauses; 1 subclause = 1 topic; no duplicates.
"""
    },

    "delivery_terms": {
        "ru": """
=== TOPIC CHECKLIST (УСЛОВИЯ ПОСТАВКИ) ===
Каждый подпункт — новая тема. Не уходи в оплату/ответственность/споры.
Покрой разные аспекты поставки, например:
- срок поставки и как он считается (от даты договора/аванса/спецификации — только по форме)
- место поставки / пункт поставки
- Incoterms (если применимо) и ссылка на редакцию (без “лишних” терминов)
- частичные поставки / партии
- переход рисков
- переход права собственности
- упаковка и маркировка
- транспорт/перевозчик/документы на отгрузку
- обязанности по погрузке/разгрузке (общо)
- график поставки (если применимо)
- приемка при поставке (только связка, без детального раздела приемки)
- хранение/расходы при задержке приемки покупателем (общо)
Требование: 20–30 подпунктов; 1 подпункт = 1 тема; без дублей.
Начинай подпункты разными фразами. 
Избегай повторов, например “Поставка производится…”, “Поставщик несет ответственность…”.
""",
        "en": """
=== TOPIC CHECKLIST (DELIVERY TERMS) ===
Each subclause must introduce a NEW delivery topic. Do not drift into payment/liability/disputes.
Cover distinct topics such as:
- delivery term and how it is calculated (only per form triggers)
- delivery place / delivery point
- Incoterms (if applicable) + edition reference
- partial shipments / batches
- transfer of risk
- transfer of title
- packaging and marking
- transport / carrier / shipping documents
- loading/unloading allocation (generic)
- delivery schedule (if applicable)
- linkage to acceptance (high-level only)
- storage/costs if Buyer delays taking delivery (generic)
- Do NOT reference other sections/articles/subclauses of this Contract.
- Do NOT use phrases: "as per section", "as specified in", "in accordance with section", "to subclause above/below".
Target 20–30 subclauses; 1 subclause = 1 topic; no duplicates.
"""
    },
}


def get_section_checklist(section_id: str, lang: str) -> str:
    """
    Returns checklist text for the given section_id and language.
    - section_id: e.g. "definitions", "payment_terms", "delivery_terms"
    - lang: "ru" or "en" (fallback to "ru" if missing)
    """
    sid = (section_id or "").strip().lower()
    lg = (lang or "ru").strip().lower()

    block = SECTION_CHECKLISTS.get(sid)
    if not block:
        return ""

    return (block.get(lg) or block.get("ru") or "").strip()
