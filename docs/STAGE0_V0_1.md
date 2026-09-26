# MONEY OS v0.1 — Stage 0: исполнимый контракт

**Scope:** только определения, чистые доменные проверки и фиксированные synthetic fixtures. Никакого HTTP, persistence, ORM, миграций, запуска БД, LLM или runtime integration. Stage 1–11 не выполнены. Это не Technical DONE приложения и не market validation.

## Канонические определения и запуск

- [definitions.py](../contracts/v0_1/definitions.py): закрытый набор сущностей и полей. Все объявленные поля обязательны, неизвестные свойства запрещены, nullable указан явно, приведения типов нет. Boolean не считается integer. Это явные stdlib-проверки конкретных записей, не универсальный schema framework.
- [invariants.py](../contracts/v0_1/invariants.py): ссылки и run scope, DAG, цитаты/хеши, арифметика, временные и межсущностные правила, отдельный TEST gate и сравнение добавочных снимков.
- [test_contract.py](../tests/stage0/test_contract.py): только Stage 0 unittest; не импортирует приложение. Python 3.10+; фактически проверено на Python 3.14.6. Внешних зависимостей нет.
- [index.json](../tests/stage0/fixtures/index.json): полный список 75 acceptance inputs. Каждый input содержит базовый полный снимок, явные замены/удаления по пути, ожидаемые structure/graph/gate, invariant и semantic oracle. Тест материализует именно эти данные, а не генерирует сценарии.

Точная команда из корня репозитория:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/stage0 -v

Фактический прогон 2026-09-26: **84 tests, OK** (75 acceptance cases + 9 проверок снимков). До расширения набора также выполнен успешный прогон 74 tests. Runtime tests не запускались.

Финальный повтор после документации: **84 tests in 0.160s, OK**, exit code 0. Проверка локальных Markdown-ссылок: PASS. Проверка scope по исходному baseline: **91 новый файл**, изменены только [ARCHITECTURE_V0_1.md](ARCHITECTURE_V0_1.md) и [IMPLEMENTATION_PLAN_V0_1.md](IMPLEMENTATION_PLAN_V0_1.md), удалений нет; остальные **23 исходных файла побайтово неизменны**, включая runtime, конфигурацию, requirements и scripts. Новые файлы: 3 определения контракта, этот документ, тестовый модуль, 75 acceptance inputs, их индекс, 8 полных snapshots и 2 намеренно плохих JSON-входа.

## Полные E2E snapshots

| Снимок | Назначение |
|---|---|
| [golden.json](../tests/stage0/fixtures/golden.json) | QUERY → SOURCES → OBSERVATIONS → CLAIMS → EVIDENCE → PROBLEM → OPPORTUNITY → TEST → Manual Test → TestArtifact → sent → responded → rejected → outcome feedback |
| [negative_research.json](../tests/stage0/fixtures/negative_research.json) | Валидное отрицательное исследование: достаточное дешёвое решение, incomplete candidate и INVESTIGATE |
| [negative_test_attempt.json](../tests/stage0/fixtures/negative_test_attempt.json) | Отдельный полный вход попытки TEST: структура/граф валидны, gate отклоняет отсутствие остаточного разрыва |
| [empty_research.json](../tests/stage0/fixtures/empty_research.json) | Недостаточно данных, без Problem/Opportunity |
| [snippet_research.json](../tests/stage0/fixtures/snippet_research.json) | Crawl неуспешен, snippet сохранён, Opportunity отсутствует |
| [candidate.json](../tests/stage0/fixtures/candidate.json) | Исследовательский кандидат без решения; валидность не даёт разрешения TEST |
| [two_versions.json](../tests/stage0/fixtures/two_versions.json) | Добавлена вторая неизменяемая версия, sent по-прежнему указывает первую |
| [semantic_forgery.json](../tests/stage0/fixtures/semantic_forgery.json) | Ложная сумма с существующей, но нерелевантной цитатой: граф валиден, oracle/review отвергает смысл и TEST |

Все операторы, получатели, компании, числа, источники и события здесь **synthetic**, включая якобы состоявшиеся отправки/оплаты. Домены зарезервированы в зоне .example; реальных контактов, отправок и платежей нет. Флаг наследуется и сверяется во всех локальных сущностях и плане получателя.

## Принятые уточнения контракта

1. **Три разных уровня.** S-* — закрытая структура/типы; G-* — граф, происхождение и арифметика; T-* — разрешение TEST на основании записанного human review. Semantic oracle в fixture — явное ожидаемое человеческое прочтение текста, а не результат NLP. Проверки не доказывают entailment. Даже human attestation не превращает предположение или synthetic текст в реальный факт.
2. **Идентификаторы.** Непустые строковые ID уникальны среди всех сущностей внутри одного снимка, все ссылки локальны и типизированы коллекцией. Чужие Source и Claim отвергаются отдельно. Cross-run ссылки разрешены только для родительского run и memory snapshots; их существование в хранилище здесь не проверяется. Нет требований UUID или новой схемы БД.
3. **Query/Run.** Query вложен в Run; фиксируются основной/контрзапрос, ограничения, лимиты 8/5, состояние, завершение/ошибка/этап, версия досье, модель/prompt/schema и фактические строки model input/output. Ручная фикстура имеет пустой model IO и явно отсутствующую модель, не выдуманный LLM-вызов. Повтор анализа — новый run, не редактирование закрытого досье.
4. **Текст и цитаты.** Сохраняется точный Unicode-текст без NFC/NFKC и без замены переносов. Диапазон — нулевой полуинтервал по Unicode code points, не UTF-8 bytes, UTF-16 units или graphemes. Хеш SHA-256 от точного UTF-8; lone surrogates недопустимы. Нельзя нормализовать после фиксации координат. Размер обрезанного снимка и ограничение явны; snippet никогда не поддерживает прямой fact. Дата публикации nullable, время получения её не заменяет.
5. **Знание.** Fact требует direct supports к page Observation. Inference требует посылки, rationale/falsifier и хотя бы один путь к наблюдаемому fact; unknown-посылки допустимы как условность, но одни unknown не образуют наблюдаемую опору. Estimate имеет два типизированных входа из fact/estimate, которые точно совпадают с referenced quantities. Unknown имеет причину, контекст и следующую проверку, но не value и не supports, изображающий доказанное значение. Пустой контекст допустим для вопроса оператора и не считается опорой.
6. **Денежные типы.** Различаются количество денег, ставка денег/час, часы, счётчик, безразмерное отношение; у денег обязательна валюта и явен период. Decimal хранится десятичной строкой (до 18 целых и 6 дробных знаков), не float, exponent, NaN или Infinity. Валюта — трёхбуквенный uppercase код формы ISO, без скачивания реестра. Тариф, трудозатраты, оценка потерь, цена теста и наблюдаемый платёж не отождествляются: тип числа плюс scope/текст/источник и review задают экономический смысл. Число в произвольной прозе нельзя автоматически распознать как корректный факт.
7. **Безопасная арифметика.** Только четыре именованные операции с двумя операндами; нет eval, AST языка формул, функций или произвольного кода. Сложение/вычитание — одинаковые размерности; умножение — часы × ставка либо безразмерный множитель; деление — на безразмерный множитель. Конвертации валют/периодов нет. Precision 50, inexact/rounded и нулевой делитель отвергаются, результат должен точно совпасть. Диапазон в единицах результата обязан содержать результат, но является явно указанным сценарием/допущением, не вычисленной вероятностью. Для более сложной оценки нужны отдельные Claims, не расширение языка.
8. **Независимость источников.** Консервативное объединение по declared origin, точному final URL или SHA-256 транзитивно; два репринта не увеличивают число групп. Число групп не доказывает независимость. Каноникализация URL и обнаружение неуказанных репринтов требуют будущих адаптеров/review.
9. **Содержательные поля.** Problem и Opportunity имеют полный закрытый набор Claim-ссылок. Неизвестность означает incomplete candidate, а не пропущенное поле. Максимум один Problem/Opportunity на run; при отсутствии наблюдаемой опоры — insufficient_evidence без обоих. Наличие кандидата не равняется разрешению TEST.
10. **TEST gate.** Только human, объяснение, review всех Claims небольшого досье, источников, противоречий и рисков; подтверждённая проблема, достижимая роль, гипотеза, полезный результат, план артефакта, success/kill, срок и денежный предел. Unknown cost не требует искусственного «полного расчёта экономики». Unknown buyer допустим при явном объяснении стратегии выяснить authority и подтверждённой достижимости получателя. Достаточное existing solution запрещает TEST, если отсутствует reviewed fact остаточного разрыва и отдельное подтверждение. Смысл стратегии и честность review остаются за человеком.
11. **План ≠ артефакт.** При решении нужен план, не уже подготовленный документ. Manual Test следует TEST и точно копирует одобренный план, один тест на решение и один получатель. TestArtifact создаётся после теста. Одна запись — одна immutable версия; номера последовательны, новая версия имеет новый ID и previous-version ID. Text имеет хеш; link — описание версии без выдуманного хеша нескачанного содержимого. Доступность и неизменность внешнего URL не гарантируются.
12. **События.** Ровно семь variants, подготовка не входит в журнал. Первое внешнее действие — sent с точным artifact ID того же теста; остальные события требуют sent, interested/rejected ещё и responded. Есть время события и записи. No-response — ручная проверка не раньше deadline и без уже известного ответа на тот момент; поздний ответ добавляется. Meeting различает scheduled/held. Paid — положительные деньги, дата, назначение и основание; это ручная запись, не банковская сверка. При исправлении сохраняется прежнее событие и добавляется same-kind correction с причиной.
13. **Неизменяемость.** Сравнение двух полных snapshots запрещает изменения/удаления существующих записей, включая пересчитанный хеш артефакта/источника, и новые research-записи в закрытом run. Один изолированный snapshot не может доказать отсутствие скрытой прошлой версии. Транзакции, уникальность клиентских ключей, идемпотентность HTTP и storage enforcement остаются будущей реализацией.
14. **Feedback/память.** Research feedback ссылается на Decision, outcome — на Event и Test, оба — на Opportunity и Claims. Переклассификация outcome в research без смены закрытого состава полей отвергается. Memory input — не локальный Source/Claim: это до 12 явно выбранных human снимков с origin run, feedback ID, типом, текстом, SHA-256 и временем выбора до запуска. Наличие внешней записи, её версия и восстановление из БД — не Stage 0. Feedback автоматически не становится evidence.
15. **Время и provenance.** Все timestamps с timezone и секундами, сравнения по моментам времени, не строкам. Общий synthetic flag/actor/created-at обязателен. Ручные решения, артефакты, события и feedback не могут иметь model actor. Это ограничение данных, не authentication/authorization; подделку actor будущий API должен предотвращать отдельно.

## Неоднозначности и намеренно непроверяемое

- Достоверность цитаты как высказывания автора, семантическое следование, качество проблемы/полезность артефакта, реальный budget authority, достаточность существующего решения и честность оплаты проверяет человек. Наличие строки «reviewed» не доказывает эти свойства. Фикстуры задают oracle; согласование реальным оператором ещё не происходило.
- Низкая цена сама по себе не запрещает TEST: важна адекватность решения и остаточный разрыв. Unknown buyer не автоматически блокирует exploratory test; выбор достижимой роли и стратегия должны быть обоснованы. Нет произвольного порога стоимости, числа независимых источников или confidence score.
- Арифметические N-* cases изолируют форму/единицы; их oracle прямо указывает отсутствие семантического review изменённых количеств. Они не принимаются как рыночные факты или разрешение TEST.
- Prompt injection fixture проверяет недоверенный content и контракт результата; не запускает модель, не обещает автоматическую устойчивость live LLM. Форма URL не является SSRF-защитой, DNS/redirect/robots policy здесь не проверяются.
- Коррекции не реализуют вычисление «актуального коммерческого состояния»: история остаётся явной, правила пересмотра последующих интерпретаций требуют будущего оператора/API. Никаких автоматических transitions, отправок, платежей или таймеров.
- Dossier ID/version и два снимка выражают контракт неизменяемости, не заменяют storage versioning. Legacy migration, concurrency, idempotency, restart/backup и runtime memory loop не реализованы и не считаются прошедшими.
- Git metadata отсутствует в предоставленном каталоге: Git diff недоступен. Scope проверяется сравнением SHA-256 исходных 25 файлов с исходным baseline; разрешены только два точечных изменения общих docs и новые Stage 0 файлы. Проверка не является Git-аудитом истории.

## Acceptance matrix

S/G — структура/граф; «да/нет» обозначает expected validity. Gate: «—» не запрашивался, «да» разрешён, «нет» отклонён. Каждый кликабельный input содержит полный набор изменений, oracle, причину и invariant; базовые snapshots приведены выше. Ожидаемая невалидность — успешный тест отказа, не ошибка тестового прогона.

| ID / input | Сценарий / причина | S/G | TEST gate | Invariant |
|---|---|---|---|---|
| [A01](../tests/stage0/fixtures/cases/A01.json) | Дословная Unicode цитата ведёт к page snapshot; утверждение ограничено заявлением synthetic компании. | да/да | — | G-QUOTE |
| [A02](../tests/stage0/fixtures/cases/A02.json) | Тариф является отрицательным аргументом к широкому wedge; остаточный разрыв и objections сохраняются. | да/да | — | G-REF |
| [A03](../tests/stage0/fixtures/cases/A03.json) | 12.50 USD/hour и 5.00 USD/month — заявленные synthetic ставка и тариф, не потери и не платёж. | да/да | — | G-FACT |
| [A04](../tests/stage0/fixtures/cases/A04.json) | Стоимость unknown не обнуляется и не блокирует дешёвый тест неизвестности. | да/да | — | G-UNKNOWN |
| [A05](../tests/stage0/fixtures/cases/A05.json) | Пять URL дают три группы происхождения, не пять независимых подтверждений. | да/да | — | G-FAMILIES |
| [A06a](../tests/stage0/fixtures/cases/A06a.json) | Snippet не повышается до page; нет Opportunity. | да/да | — | G-ANCHOR |
| [A06b](../tests/stage0/fixtures/cases/A06b.json) | Snippet не поддерживает fact | да/нет | — | G-FACT |
| [A07](../tests/stage0/fixtures/cases/A07.json) | Источников нет: допустим insufficient_evidence без Problem/Opportunity. | да/да | — | G-ANCHOR |
| [A08](../tests/stage0/fixtures/cases/A08.json) | Текст сохранён с trust=untrusted; не создаёт Decision, сумму или сетевое действие. Live LLM robustness не проверяется. | да/да | — | S-ENUM |
| [A09](../tests/stage0/fixtures/cases/A09.json) | Положительное и отрицательное отношения сосуществуют; schema не решает спор. | да/да | — | G-REF |
| [A10](../tests/stage0/fixtures/cases/A10.json) | Ценный результат ссылается на c-work и c-gap; rationale и falsifier обязательны. | да/да | — | G-DAG |
| [A11](../tests/stage0/fixtures/cases/A11.json) | 4 hours/month × 12.50 USD/hour = 50.00 USD/month; диапазон 40–60 — допущение, не статистика. | да/да | — | G-ARITHMETIC |
| [A12](../tests/stage0/fixtures/cases/A12.json) | Оценка с unknown входом запрещена | да/нет | — | G-ESTIMATE-INPUT |
| [A13](../tests/stage0/fixtures/cases/A13.json) | Есть reason/context/next_check; поля value у unknown нет. | да/да | — | G-UNKNOWN |
| [A14a](../tests/stage0/fixtures/cases/A14a.json) | Чужой Source ID | да/нет | — | G-REF |
| [A14b](../tests/stage0/fixtures/cases/A14b.json) | Чужой Claim ID | да/нет | — | G-REF |
| [A15](../tests/stage0/fixtures/cases/A15.json) | Несуществующая цитата | да/нет | — | G-QUOTE |
| [A16](../tests/stage0/fixtures/cases/A16.json) | Цикл Claims | да/нет | — | G-DAG |
| [A17a](../tests/stage0/fixtures/cases/A17a.json) | Нет прямой цитаты. Денежная сумма не становится fact. | да/нет | — | G-FACT |
| [A17b](../tests/stage0/fixtures/cases/A17b.json) | Граф валиден, но human review/oracle отвергает смысл; TEST запрещён. Схема не доказывает entailment. | да/да | нет | T-SEMANTICS |
| [A18](../tests/stage0/fixtures/cases/A18.json) | Бюджетный плательщик unknown; есть достижимая роль и явная стратегия выяснить authority, нулевой бюджет. Это разрешённый synthetic TEST, не подтверждённая экономика. | да/да | да | T-PLAN |
| [A19a](../tests/stage0/fixtures/cases/A19a.json) | Валидный incomplete candidate с INVESTIGATE, не разрешение TEST. | да/да | — | G-COMPLETENESS |
| [A19b](../tests/stage0/fixtures/cases/A19b.json) | Adequate solution без доказанного остаточного разрыва блокирует TEST. | да/да | нет | T-EXISTING |
| [E00](../tests/stage0/fixtures/cases/E00.json) | Golden сквозной цикл до rejected/outcome | да/да | да | G-EVENT |
| [E-sent](../tests/stage0/fixtures/cases/E-sent.json) | Вариант sent | да/да | да | G-EVENT |
| [E-responded](../tests/stage0/fixtures/cases/E-responded.json) | Вариант responded | да/да | да | G-EVENT |
| [E-interested](../tests/stage0/fixtures/cases/E-interested.json) | Вариант interested | да/да | да | G-EVENT |
| [E-rejected](../tests/stage0/fixtures/cases/E-rejected.json) | Вариант rejected | да/да | да | G-EVENT |
| [E-no_response](../tests/stage0/fixtures/cases/E-no_response.json) | Вариант no_response | да/да | да | G-EVENT |
| [E-meeting](../tests/stage0/fixtures/cases/E-meeting.json) | Вариант meeting | да/да | да | G-EVENT |
| [E-paid](../tests/stage0/fixtures/cases/E-paid.json) | Вариант paid | да/да | да | G-EVENT |
| [E-prepared](../tests/stage0/fixtures/cases/E-prepared.json) | artifact_prepared не Market Event | нет/нет | — | S-ENUM |
| [E-no-version](../tests/stage0/fixtures/cases/E-no-version.json) | sent без версии | нет/нет | — | S-SHAPE |
| [E-other-test](../tests/stage0/fixtures/cases/E-other-test.json) | sent с артефактом другого теста | да/нет | — | G-ARTIFACT-TEST |
| [E-two-versions](../tests/stage0/fixtures/cases/E-two-versions.json) | Новая версия не меняет artifact-1 или ссылку старого sent. | да/да | да | G-IMMUTABLE |
| [E-early-silence](../tests/stage0/fixtures/cases/E-early-silence.json) | no_response до deadline | да/нет | — | G-DEADLINE |
| [D-model](../tests/stage0/fixtures/cases/D-model.json) | Модель не принимает Decision | да/нет | — | G-HUMAN |
| [F-research](../tests/stage0/fixtures/cases/F-research.json) | Research feedback отдельно от outcome | да/да | да | G-FEEDBACK |
| [F-outcome](../tests/stage0/fixtures/cases/F-outcome.json) | Outcome feedback с Event/Test | да/да | да | G-FEEDBACK |
| [F-not-research](../tests/stage0/fixtures/cases/F-not-research.json) | Outcome нельзя переименовать в research | нет/нет | — | S-SHAPE |
| [D-REJECT](../tests/stage0/fixtures/cases/D-REJECT.json) | REJECT отдельно от рыночного события | да/да | — | G-HUMAN |
| [D-INVESTIGATE](../tests/stage0/fixtures/cases/D-INVESTIGATE.json) | INVESTIGATE отдельно от рыночного события | да/да | — | G-HUMAN |
| [D-problem](../tests/stage0/fixtures/cases/D-problem.json) | TEST при неподтверждённой проблеме | да/да | нет | T-PROBLEM |
| [D-plan](../tests/stage0/fixtures/cases/D-plan.json) | TEST без плана артефакта | да/да | нет | T-PLAN |
| [D-review](../tests/stage0/fixtures/cases/D-review.json) | TEST без review | да/да | нет | T-REVIEW |
| [D-recipient](../tests/stage0/fixtures/cases/D-recipient.json) | TEST без достижимого получателя | да/да | нет | T-RECIPIENT |
| [S-unknown-property](../tests/stage0/fixtures/cases/S-unknown-property.json) | Unknown property отклоняется | нет/нет | — | S-SHAPE |
| [S-bool-int](../tests/stage0/fixtures/cases/S-bool-int.json) | Boolean не integer | нет/нет | — | S-TYPE |
| [S-naive-time](../tests/stage0/fixtures/cases/S-naive-time.json) | Timestamp без timezone | нет/нет | — | S-TIME |
| [S-unknown-value](../tests/stage0/fixtures/cases/S-unknown-value.json) | Unknown не имеет value | нет/нет | — | S-SHAPE |
| [G-foreign-run](../tests/stage0/fixtures/cases/G-foreign-run.json) | Entity другого run | да/нет | — | G-SCOPE |
| [G-hash](../tests/stage0/fixtures/cases/G-hash.json) | Хеш снимка не совпадает | да/нет | — | G-HASH |
| [G-currency](../tests/stage0/fixtures/cases/G-currency.json) | Смешение валют | да/нет | — | G-UNITS |
| [G-arithmetic](../tests/stage0/fixtures/cases/G-arithmetic.json) | Неверный Decimal результат | да/нет | — | G-ARITHMETIC |
| [G-float](../tests/stage0/fixtures/cases/G-float.json) | Число float вместо Decimal строки | нет/нет | — | S-TYPE |
| [G-missing-input](../tests/stage0/fixtures/cases/G-missing-input.json) | Отсутствует операнд | нет/нет | — | S-FORMULA |
| [G-unsafe-formula](../tests/stage0/fixtures/cases/G-unsafe-formula.json) | Исполняемая формула запрещена | нет/нет | — | S-ENUM |
| [E-response-without-sent](../tests/stage0/fixtures/cases/E-response-without-sent.json) | Ответ без отправки | да/нет | — | G-REF |
| [E-no-response-link](../tests/stage0/fixtures/cases/E-no-response-link.json) | Отказ без responded | да/нет | — | G-REF |
| [E-paid-zero](../tests/stage0/fixtures/cases/E-paid-zero.json) | Paid с нулём | нет/нет | — | S-PAYMENT |
| [E-before-artifact](../tests/stage0/fixtures/cases/E-before-artifact.json) | Отправка до подготовки | да/нет | — | G-TIME |
| [G-synthetic-mix](../tests/stage0/fixtures/cases/G-synthetic-mix.json) | Нельзя смешать synthetic и real | да/нет | — | G-SYNTHETIC |
| [M-snapshot](../tests/stage0/fixtures/cases/M-snapshot.json) | Исторический feedback хранится как выбранный снимок с внешним origin run; не становится локальным Evidence. | да/да | — | G-MEMORY |
| [S-malformed](../tests/stage0/fixtures/cases/S-malformed.json) | Неполный JSON | нет/нет | — | S-JSON |
| [S-duplicate-json](../tests/stage0/fixtures/cases/S-duplicate-json.json) | Дублирующийся JSON key | нет/нет | — | S-JSON |
| [E-late-response](../tests/stage0/fixtures/cases/E-late-response.json) | Поздний ответ дописывается после no_response | да/да | да | G-EVENT |
| [E-correction](../tests/stage0/fixtures/cases/E-correction.json) | Исправление отказа добавочно, прежняя запись сохранена | да/да | да | G-EVENT |
| [E-meeting-held](../tests/stage0/fixtures/cases/E-meeting-held.json) | Состоявшаяся встреча отличается от запланированной | да/да | да | G-EVENT |
| [G-no-anchor](../tests/stage0/fixtures/cases/G-no-anchor.json) | Inference только из unknown не имеет наблюдаемой опоры | да/нет | — | G-ANCHOR |
| [N-add](../tests/stage0/fixtures/cases/N-add.json) | Безопасная арифметика add; проверка единиц, не смысла | да/да | — | G-ARITHMETIC |
| [N-subtract](../tests/stage0/fixtures/cases/N-subtract.json) | Безопасная арифметика subtract; проверка единиц, не смысла | да/да | — | G-ARITHMETIC |
| [N-multiply](../tests/stage0/fixtures/cases/N-multiply.json) | Безопасная арифметика multiply; проверка единиц, не смысла | да/да | — | G-ARITHMETIC |
| [N-divide](../tests/stage0/fixtures/cases/N-divide.json) | Безопасная арифметика divide; проверка единиц, не смысла | да/да | — | G-ARITHMETIC |
| [N-zero-divisor](../tests/stage0/fixtures/cases/N-zero-divisor.json) | Деление на ноль запрещено | да/нет | — | G-ARITHMETIC |
| [N-inexact](../tests/stage0/fixtures/cases/N-inexact.json) | Неявное округление бесконечной десятичной дроби запрещено | да/нет | — | G-ARITHMETIC |
