# src/prompts/topic_checklists.py

FORM_TOPIC_CHECKLIST = {

    # =====================================================
    # DEFINITIONS
    # =====================================================
    "definitions": {
        "ru": """
Сформируй 14–20 кратких определений.
Каждый подпункт — отдельный термин.
Без повторов.
Покрой: стороны, предмет, документы, цена, поставка, оплата, приемка, гарантия, споры, форс-мажор.
""",
        "en": """
Write 14–20 short distinct definitions.
One term per line. No duplicates.
Cover: parties, goods, documents, price, delivery, payment, acceptance, warranty, disputes, force majeure.
"""
    },

    # =====================================================
    # SUBJECT
    # =====================================================
    "subject_of_contract": {
        "ru": """
Опиши предмет договора 14–20 подпунктами.
Покрой: поставка товара, приемка, комплектность, качество, документы, упаковка/маркировка, переход рисков/собственности, частичные поставки, спецификация как часть договора.
Не упоминай оплату или ответственность.
""",
        "en": """
Describe the subject in 14–20 clauses.
Cover: delivery, acceptance, quality, completeness, documents, packaging/marking, transfer of title/risk, partial shipments, specification as integral part.
Avoid payment or liability.
"""
    },

    # =====================================================
    # PRICE
    # =====================================================
    "price_and_taxes": {
        "ru": """
Раскрой цену и налоги 16–20 пунктами.
Покрой: валюта, цена договора, база цены, состав цены, НДС/налоги, документы цены, изменение цены только по соглашению, отсутствие скрытых платежей.
Без сроков оплаты.
""",
        "en": """
Describe price and taxes in 16–20 clauses.
Cover: currency, contract price, price basis, inclusions/exclusions, VAT/taxes, price documents, written price changes only, no hidden fees.
No payment timing.
"""
    },

    # =====================================================
    # ACCEPTANCE
    # =====================================================
    "acceptance_and_inspection": {
        "ru": """
Опиши приемку 16–20 пунктами.
Покрой: осмотр, сроки, место, документы приемки, проверка количества и качества, фиксация дефектов, уведомления, частичные партии, совместная инспекция.
Без гарантий и штрафов.
""",
        "en": """
Describe acceptance in 16–20 clauses.
Cover: inspection, timing, place, acceptance documents, quantity/quality checks, defect recording, notices, partial shipments, joint inspection.
No warranty or penalties.
"""
    },

    # =====================================================
    # WARRANTIES
    # =====================================================
    "warranties": {
        "ru": """
Опиши гарантию 16–20 пунктами.
Покрой: срок гарантии, начало, гарантийный случай, уведомление о дефектах, ремонт/замена, исключения, расходы, документы, обязанности сторон.
Без штрафов.
""",
        "en": """
Describe warranty in 16–20 clauses.
Cover: period, start, warranty case, defect notice, repair/replacement, exclusions, costs, documents, cooperation duties.
No penalties.
"""
    },

    # =====================================================
    # LIABILITY
    # =====================================================
    "liability_and_penalties": {
        "ru": """
Раскрой ответственность 18–22 пунктами.
Покрой: общий принцип ответственности, убытки, лимиты, исключения косвенных потерь, нарушения обязательств, претензии, форс-мажор, иные средства защиты.
Не придумывай ставки/проценты.
""",
        "en": """
Describe liability in 18–22 clauses.
Cover: general liability, damages, caps, exclusions of indirect losses, breaches, claims, force majeure, other remedies.
Do not invent rates or percentages.
"""
    },

    # =====================================================
    # FORCE MAJEURE
    # =====================================================
    "force_majeure": {
        "ru": """
Опиши форс-мажор 16–20 пунктами.
Покрой: определение событий, уведомление, доказательства, приостановление обязательств, продление сроков, минимизация последствий, прекращение, освобождение от ответственности.
""",
        "en": """
Describe force majeure in 16–20 clauses.
Cover: events definition, notice, evidence, suspension, time extension, mitigation, termination right, liability relief.
"""
    },

    # =====================================================
    # LAW & DISPUTES
    # =====================================================
    "governing_law_and_disputes": {
        "ru": """
Опиши применимое право и споры 14–18 пунктами.
Покрой: применимое право, суд/подсудность, переговоры/претензии, язык, расходы, обеспечительные меры, разделимость положений, сохранение обязательств после прекращения.
""",
        "en": """
Describe governing law and disputes in 14–18 clauses.
Cover: governing law, venue, negotiation/claims, language, costs, interim relief, severability, survival.
"""
    },
}
