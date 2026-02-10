Данный раздел описывает, как воспроизвести работу проекта и где посмотреть результаты генерации.

1. Установка окружения

Требования
- ОС: Windows / Linux / macOS
- Python: 3.11 (рекомендуется)
- Доступ к локальной машине или Google Colab

Клонирование репозитория

git clone <https://github.com/NikolayGRIN/Contract_LLM_Creator/tree/main>
cd Contract-LLM-Creator

2. Настройка модели (Model Setup)

Проект использует локальные языковые модели (без облачных API).

Шаг 1. Скачать GGUF-модель

Рекомендуемая модель: Qwen2.5-7B-Instruct (GGUF, q4_k_m)

Пример файлов:qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
              qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf

Шаг 2. Разместить модель

Рекомендуемая структура: Contract-LLM-Creator/models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf

Шаг 3. Указать путь к модели

В файле src/config.py: 

LOCAL_GGUF_MODEL_PATH = "models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
N_CTX = 4096
N_THREADS = 8
TEMPERATURE = 0.3
TOP_P = 0.92
MAX_TOKENS = 1600

# Для Google Colab (опционально):
# N_GPU_LAYERS = 35



3. Запуск генерации договора
Входные данные
Основной файл параметров: form_input.json (в корне репозитория)

В нём задаются:
- язык генерации (language_mode: "ru" или "en"),
- условия оплаты,
- условия поставки (например, delivery_term_days),
- прочие параметры договора.

Запуск: python run_generate.py


4. Исполняемые файлы
4.1. Главный исполняемый скрипт run_generate.py
Роль: главный вход в систему
Что делает:
загружает form_input.json
валидирует форму (form_validate)
запускает retrieval (BM25)
строит prompt’ы
вызывает локальную LLM
применяет валидаторы
сохраняет итог в out.txt
4.2. Генерация (prompt builders)
- src/generation/payment_terms_generate.py  
- src/generation/delivery_terms_generate.py 
Роль:
формируют управляемые prompt'ы для разделов Payment Terms и Delivery Terms
учитывают form_input.json
обеспечивают ≥ 20 подпунктов
поддерживают RU / EN
задают структуру, ограничения, план тем
4.3. Валидация (контроль качества)
- src/validation/payment_terms_validator.py
- src/validation/delivery_terms_validator.py
Роль:
проверяют для Payment Terms и Delivery Terms 
количество подпунктов, формат нумерации,
запрет тем (disputes, liability и т.д.), минимальный объём,
логическую консистентность и др.
4.4. Retrieval (корпусный поиск) - src/retrieval/bm25.py
Роль:
загрузка corpus_sections.jsonl
фильтрация релевантных секций
BM25-поиск
диверсификация результатов
маскирование переменных формы
4.5. Очистка прецедентов - src/cleaning/precedent_cleaner.py
Роль:
удаляет дубликаты
нормализует текст
подготавливает корпусные фрагменты для prompt’а
4.6. Работа с формой 
- src/validation/form_validate.py
Роль:
валидирует form_input.json по JSON Schema 
- src/form_schema/contract_form_v1.schema.json
Роль:
формальное описание входных данных
4.7. LLM-интерфейс (оффлайн)
- src/generation/local_llm.py
Роль:
обёртка над llama-cpp-python
единый интерфейс для CPU / GPU
retry-логика с валидатором
- src/config.py
Роль:
путь к модели
параметры инференса
единая конфигурация для ноутбука и Colab
4.8. Данные и результаты 
- corpus_sections.jsonl
Роль:
основной корпус для retrieval
демонстрация реальных договоров

- form_input.json
Роль:
пример пользовательского запроса
ключ к воспроизводимости

5. Где смотреть результаты
Основной результат: out.txt — итоговый сгенерированный текст договора
(разделы Payment Terms и Delivery Terms)

Примеры результатов

results/Русский.txt — пример генерации на русском языке

results/English.txt — пример генерации на английском языке

Диагностические файлы (для анализа)

Директория debug/:
*_prompt.txt — использованные промпты
*_precedents_raw.txt — найденные прецеденты (BM25)
*_precedents_clean.txt — очищенные прецеденты
*_llm_bad.txt — отклонённые версии генерации
*_llm_used_attempts.txt — число попыток генерации

6. Что демонстрирует результат
Репозиторий демонстрирует:
полностью оффлайн генерацию договорных разделов,
использование реального корпусного retrieval (BM25),
контролируемую генерацию с валидацией структуры,
поддержку русского и английского языков,
воспроизводимость результатов без облачных сервисов.