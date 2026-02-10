# src/prompts/topic_checklists.py
# One dictionary: key = section_id (as used in your pipeline)

SECTION_CHECKLISTS = {
    # ---------------------------------------------------------
    # FORM-BASED SECTIONS
    # ---------------------------------------------------------
    "definitions": {
        "ru": """
=== TOPIC CHECKLIST (ОПРЕДЕЛЕНИЯ) ===
Сформируй определения, каждое — отдельный подпункт. Покрой РАЗНЫЕ термины, без повторов и перефразов одного и того же:
- Стороны: “Поставщик”, “Покупатель”, общий термин “Сторона/Стороны”, “Аффилированные лица” (если упоминаются).
- Договор/Контракт, дата заключения, дата вступления в силу, срок действия (как понятия, без дат).
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
- Гарантия/гарантийный случай, гарантийный срок, начало гарантии, способ устранения (ремонт/замена).
- Форс-мажор, уведомление, подтверждающие документы (как понятия).
- Спор/претензия/требование, компетентный суд/арбитраж (как понятия).
- Конфиденциальная информация (если упоминается), персональные данные (если упоминаются).
Требование: 14–20 определений; избегай “определено в разделе …”; каждое определение — самостоятельное, без воды.
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
At least 14–20 definitions; avoid “as defined in section…”.
"""
    },

    "subject_of_contract": {
        "ru": """
=== TOPIC CHECKLIST (ПРЕДМЕТ ДОГОВОРА) ===
Покрой РАЗНЫЕ аспекты предмета (не уходи в оплату/ответственность/форс-мажор):
- Обязательство Поставщика поставить Товары/Оборудование по Спецификации/Приложению.
- Обязательство Покупателя принять Товары и оформить приемку документально.
- Количество/ассортимент/комплектность: “согласно Спецификации”, без лишних цифр (если не задано).
- Требование “новые, не бывшие в употреблении, не восстановленные” (общо).
- Требования к качеству: соответствие Спецификации, стандартам/сертификатам (общо).
- Документация: паспорта, инструкции, сертификаты, гарантийные талоны (общо).
- Маркировка и упаковка: общие требования, детали — в Спецификации.
- Место и способ передачи товара (общо), связь передачи с приемкой.
- Переход права собственности (общо) и момент, к которому привязан (общо, без Incoterms если не задан).
- Переход рисков (общо) и момент/условие перехода.
- Частичные поставки/партии (если допускаются) — общо.
- Сопутствующие материалы/ЗИП/расходники (если применимо) — общо.
- Возможность замены эквивалентом только по согласованию (общо).
- Указание, что Спецификация/Приложения — неотъемлемая часть договора.
- Язык документации и маркировки (общо).
- Обязанность сторон сотрудничать по техническим вопросам (общо, без услуг/обучения если не в форме).
Сделай 14–20 подпунктов; каждый — новая тема, без перефразов.
""",
        "en": """
=== TOPIC CHECKLIST (SUBJECT OF CONTRACT) ===
Cover distinct subject aspects (do not drift into payment/liability/force majeure):
- Supplier’s obligation to deliver Goods/Equipment per Specification/Annex.
- Buyer’s obligation to accept Goods and document acceptance.
- Quantity/assortment/completeness: “as per Specification” (no extra numbers if not provided).
- New goods only (not used/refurbished) (generic).
- Quality compliance: Specification and standards/certificates (generic).
- Documentation: manuals, passports, certificates, warranty documents (generic).
- Marking/packaging: general requirements; details in Specification.
- Place/method of delivery/hand-over (generic) and linkage to acceptance.
- Transfer of title (generic) and trigger event (generic).
- Transfer of risk (generic) and trigger event/condition.
- Partial shipments/batches (if allowed) (generic).
- Optional spare parts/consumables/accessories (generic if applicable).
- Substitution/equivalents only by mutual agreement (generic).
- Specification/Annex as integral part of Contract.
- Language of documentation/labels (generic).
- Parties’ cooperation on technical matters (generic; avoid services/training unless in the form).
Target 14–20 subclauses; each is a new topic.
"""
    },

    "price_and_taxes": {
        "ru": """
=== TOPIC CHECKLIST (ЦЕНА И НАЛОГИ) ===
Не уходи в сроки/порядок оплаты (это Payment Terms). Раскрой цену и налоги разными темами:
- Валюта цены и валюта договора (как в форме).
- Общая цена договора (как в форме) или “согласуется в Спецификации/счетах”, если TBD.
- База цены (фикс/за единицу/за партию/за этап) — по форме или общо.
- Структура цены: “включает/не включает” упаковку (по форме), общо про маркировку/тару.
- НДС/VAT режим по форме: включен/начисляется сверх/не применяется — без ставок и цифр.
- Если НДС начисляется сверх — “при наличии обязанности по закону”, без процентов.
- Налоги/пошлины/сборы: распределение “если применимо”, без конкретики.
- Подтверждающий документ цены: Спецификация/Приложение/инвойсы (общо).
- Округления, единицы измерения и порядок указания цены (общо).
- Распределение цены по партиям/этапам/позициям Спецификации (общо, если применимо).
- Порядок изменения цены: только письменное соглашение/доп. соглашение (общо).
- Запрет одностороннего изменения цены (общо).
- Изменение обязательных налогов/пошлин: влияет/не влияет только по соглашению или по закону (общо, аккуратно).
- Условие о том, что цена включает обычные расходы Поставщика (общо, без перечисления “всё на свете”).
- Запрет скрытых платежей/двойного начисления/необоснованных сборов (общо).
- Курсовые вопросы: “если валюта отличается от валюты расчетов — по соглашению сторон” (общо, без формул).
- Документирование корректировок цены: доп. соглашение/спецификация/корректировочный документ (общо).
- Налоговые документы: счет-фактура/инвойс (если применимо) — общо.
Сделай 16–22 подпункта; каждый — новая тема (не повторять “Цена не изменяется…” разными словами).
""",
        "en": """
=== TOPIC CHECKLIST (PRICE AND TAXES) ===
Do not drift into payment timing (that is Payment Terms). Cover price/tax topics distinctly:
- Currency of price and contract currency (from form).
- Total contract price (from form) or “to be agreed in Specification/invoices” if TBD.
- Price basis (lump sum/per unit/per lot/per milestone) per form or generic.
- Price composition: includes/does not include packaging (per form); generic on marking/packing.
- VAT mode per form: included/added/not applicable — no rates/numbers.
- If VAT is added: “if applicable under law”, no percentages.
- Taxes/duties/fees allocation “if applicable”, no specifics.
- Price evidence: Specification/Annex/invoices (generic).
- Rounding, units, and how prices are stated (generic).
- Allocation across batches/milestones/specification items (generic if applicable).
- Price changes only by written agreement (generic).
- No unilateral price change (generic).
- Changes in mandatory taxes/duties: handled as per law and/or agreement (generic, careful).
- Price includes customary supplier costs (generic, not “everything”).
- No hidden fees / no double charging (generic).
- FX matters: if currency differs from settlement currency, handled by agreement (no formulas).
- Documentation of adjustments: amendment/specification/corrective document (generic).
- Tax documents: invoice/tax invoice where applicable (generic).
Target 16–22 subclauses; each must add a NEW topic (avoid rephrasing “price shall not change” repeatedly).
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
Сделай 16–22 подпункта; каждый — новая тема, без перефразов.
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
Target 16–22 subclauses; each is a NEW topic.
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
Сделай 16–22 подпункта; каждый — новая тема, избегай повторяющихся конструкций “Покупатель обязан…”.
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
Target 16–22 subclauses; each must add a NEW topic.
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
Сделай 18–26 подпунктов; избегай серии строк “Ответственность за …” — вариируй начальные конструкции.
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
Target 18–26 subclauses; vary sentence starters (avoid repeating “Liability for…”).
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
Сделай 16–22 подпункта; избегай повторов “В случае возникновения… стороны обязаны принять меры…” много раз.
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
Target 16–22 subclauses; avoid repeating “In case of FM the Parties shall…” many times.
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
- Исполнимость отдельных положений (severability) — общо.
- Сохранение действия отдельных обязательств после прекращения договора (survival) — общо.
- Запрет самоуправства/обязанность действовать добросовестно при урегулировании (общо).
- Никаких конкретных сроков исковой давности; можно указать “по применимому праву”.
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
- размер предоплаты (авансового платежа), сколько процентов контрактной стоимости оплачивается авансом
- момент исполнения обязательства по оплате
- валюта платежа
- банковские комиссии
- порядок выставления счетов/инвойсов
- подтверждающие документы (поставка/приемка)
- частичная/поэтапная оплата (если применимо)
- корректировочные счета/кредит-ноты
- оспаривание сумм (только механика оплаты неоспариваемой части)
- запрет/условия удержаний и зачетов 
- возврат переплаты / зачет переплаты
- сверка взаиморасчетов
- подтверждение платежей / хранение документов
- электронный документооборот по счетам
Требование: 20–30 подпунктов; 1 подпункт = 1 новая тема; без дублей.
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
Target 20–30 subclauses; 1 subclause = 1 topic; no duplicates.
"""
    },

    "delivery_terms": {
        "ru": """
=== ТРЕБОВАНИЕ К РАЗНООБРАЗИЮ СОДЕРЖАНИЯ (ОБЯЗАТЕЛЬНО) ===
Каждый подпункт должен раскрывать НОВЫЙ аспект условий поставки.
НЕЛЬЗЯ повторять или перефразировать одну и ту же тему.

Покрой РАЗНЫЕ аспекты, например:

• срок поставки и порядок его исчисления (календарные дни / перенос на рабочий день)
• основание начала отсчёта срока (вступление в силу / заказ / иное по форме)
• место поставки (как указано в форме; без выдуманных адресов)
• разрешение/запрет частичных поставок и условия
• порядок согласования графика/партии/этапов поставки
• уведомление о готовности к отгрузке и срок уведомления
• требования к упаковке, таре и сохранности
• маркировка, идентификация партий, сопроводительная информация
• погрузка/разгрузка: кто выполняет и кто несёт риски работ
• транспортировка: организация перевозки и распределение обязанностей
• переход риска случайной гибели/повреждения
• переход права собственности
• состав и форма сопроводительных документов (накладная/акт/сертификаты и т.п.)
• порядок передачи документов (электронно/оригиналы) и сроки
• приемка по количеству/качеству (если по форме требуется приемка)
• сроки приемки и порядок уведомления о несоответствиях
• последствия непредоставления мотивированных замечаний в срок (презумпция приемки)
• порядок действий при обнаружении недопоставки/повреждений при приемке
• порядок замены/допоставки и согласование сроков
• форс-мажорная логистика (задержки перевозчика) — только в рамках поставки
• инкотермс (если указан в форме), версия и приоритет над иными условиями
• ограничения: без оплаты/штрафов/споров — только доставка/отгрузка/приемка

ВАЖНО: каждый подпункт = новая самостоятельная идея.
""",
    "en": """
=== CONTENT DIVERSITY REQUIREMENT (MANDATORY) ===
Each subclause must describe a DIFFERENT aspect of Delivery/Shipment terms.
Do NOT repeat or paraphrase the same topic.

Cover DISTINCT aspects such as:

• delivery term and how it is calculated (calendar days / business day shift)
• trigger for counting the term (effective date / PO / as per form)
• place of delivery (as per form; do not invent addresses)
• partial shipments allowed/prohibited and conditions
• delivery schedule / lots / milestones and approval workflow
• readiness-to-ship notice and timing
• packaging requirements and protection
• marking / labeling / batch identification
• loading/unloading responsibilities and related risks
• transportation arrangement and duties
• transfer of risk of loss/damage
• transfer of title/ownership
• shipping/acceptance documents list and form
• document delivery method (electronic/originals) and timing
• acceptance/inspection requirements (if required by form)
• acceptance period and notice of defects/shortages
• deemed acceptance if no reasoned objections in time
• actions upon shortage/damage at delivery
• replacement / re-delivery procedure and coordination of timelines
• logistics delays (carrier issues) — only within delivery scope
• Incoterms (if provided in form), version and priority rules
• constraints: no payment/penalties/disputes — delivery scope only

IMPORTANT: every subclause must introduce a NEW rule.
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
