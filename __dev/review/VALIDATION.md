# Проверки кода и воспроизведение дефектов

Проверено 18 октября 2026 года на checkout `cb03914`, `get_codeblock` версии `0.8.0`. Восемь штатных наборов завершились успешно: **601 проверка, 0 ошибок**. Дополнительные примеры воспроизводят все десять находок из [FINDINGS.md](FINDINGS.md).

## Окружение

Основной интерпретатор — системный Python **3.14.7**, 64 bit:

```text
C:/Users/User/AppData/Local/Python/pythoncore-3.14-64/python.exe
```

По указанию пользователя зависимости установлены в системный Python. Из `get_codeblock/requirements.txt` недоставало YAML, Bash и PowerShell; остальные грамматики уже были установлены. Для тестов `split_monster` дополнительно установлен pytest 9.1.1.

| Пакет | Версия |
|---|---|
| tree-sitter | 0.26.0 |
| tree-sitter-cpp | 0.23.4 |
| tree-sitter-c-sharp | 0.23.5 |
| tree-sitter-typescript | 0.23.2 |
| tree-sitter-css | 0.25.0 |
| tree-sitter-yaml | 0.7.2 |
| tree-sitter-bash | 0.25.1 |
| tree-sitter-powershell | 0.26.4 |
| tree-sitter-python | 0.25.0 |

Указанный в документации эталонный `T:/AgentsWork/venv/Scripts/python.exe` на этой машине отсутствует. Результаты основных наборов относятся к Python 3.14, а не к эталонному 3.12.

Для отдельного примера AST fallback использован Python 3.12.14 из runtime Codex, в котором tree-sitter и грамматик нет. Из системного Python пакеты не удалялись. Это проверяет конкретное проявление R07 без грамматики, но не является полным прогоном проекта на Python 3.12.

## Штатные наборы

Команды выполнялись из `F:/WORK/ProjectStarter/__HQ/tools` системным Python. Полные stdout и stderr объединены в указанных протоколах.

| Проверка | Результат | Протокол |
|---|---:|---|
| `test/check.py --fails` | 135 passed, 0 failed | [check.log](validation/check.log) |
| `test/golden_check.py` | 14 из 14 | [golden.log](validation/golden.log) |
| `test/test_views.py` | 31 passed, 0 failed | [views.log](validation/views.log) |
| `test/test_name_resolver.py` | 36 passed, 0 failed | [names.log](validation/names.log) |
| `test/test_cpp.py --fails` | 150 passed, 0 failed | [cpp.log](validation/cpp.log) |
| `test/test_cardstamp.py` | 155 passed, 0 failed | [cards.log](validation/cards.log) |
| `test/run_restamp_fixtures.py` | 21 passed, 0 failed | [restamp.log](validation/restamp.log) |
| `-m pytest -q test/test_split_monster.py` | 59 passed | [split.log](validation/split.log) |

Сумма: **601**. Пропусков из-за отсутствующих грамматик в этих наборах нет.

Прямой запуск `test/test_split_monster.py` ничего не тестирует: в файле объявлены pytest-функции без собственного runner. Для итогового результата использован pytest, а [run_validation.py](run_validation.py) содержит соответствующую команду. Остальные семь наборов имеют собственные runner.

Воспроизводимый запуск:

```powershell
$reviewPython = 'C:/Users/User/AppData/Local/Python/pythoncore-3.14-64/python.exe'
& $reviewPython __dev/review/run_validation.py
```

Этот скрипт сохраняет протоколы и [summary.json](validation/summary.json), не меняя оракулы или исходники. Штатный restamp создаёт свои обычные результаты в игнорируемых `.actual`.

## Проверка инвариантов

### Сплошной проход граничных и небольших фикстур

```powershell
& $reviewPython -u test/sweep_invariants.py `
  test/Edge test/scriptSRC test/mdSRC test/yamlSRC test/cssSRC test/pythonSRC `
  --check-query --show 5
```

Проверены **30 файлов, 3259 непустых строк**. `CONTAIN=0`, `RANGE=0`, `CRASH=0`, `OPEN=0`, `QUERY=0`, `LEVEL=0`. Код возврата 0. Шесть `SIBLING` относятся к ожидаемым общим границам. Протокол: [sweep_edges.log](validation/sweep_edges.log).

### Выборка по всему дереву test

```powershell
& $reviewPython -u test/sweep_invariants.py --step 10 --check-query --show 4
```

Проверены **142 файла, 5267 непустых строк-якорей** с шагом 10 по физическим строкам. Результат:

```text
HIGH CONTAIN=0 RANGE=0 CRASH=9 OPEN=0 QUERY=3
LOW  LEVEL=1
INFO SIBLING=36 EMPTY=0
```

Код возврата **1**; этот прогон нельзя считать полностью зелёным. Все 12 HIGH относятся к трём старым cp1252-фикстурам `test/test__replace_in_files/fixtures`: `README.md`, `src/services/database.py`, `src/services/internal/cache.py`. Они содержат байт `0x97`, несовместимый с жёстким UTF-8 чтением get_codeblock. Проблема уже отмечена в `__dev/CONTEXT_RESTORE.md` и TRACKER; она не посчитана новой находкой.

Единственный LOW — строка 1211 `test/tsSRC2/core/schemas.ts`, `} catch (_) {}`. У `try` и `catch` общая физическая граница и одинаковый уровень; предупреждение сравнивает эти диапазоны как вложенные. Контракт допускает такие sibling-границы. Новая ошибка вложенности на этом примере не подтверждена.

Полный протокол: [sweep_sample.log](validation/sweep_sample.log). Количества строк двух sweep-прогонов пересекаются и не должны складываться как число уникальных проверенных строк.

### Остановленный сплошной проход всего дерева

Первоначальный запуск без `--step` остановлен после примерно **496 секунд CPU** из-за длительности. Он не выдал итоговую сводку и не считается завершённой проверкой. Его заменяют два явно ограниченных прогона выше. Факт остановки и точная команда сохранены в [sweep_full_attempt.json](validation/sweep_full_attempt.json). Показатель CPU не равен времени ожидания пользователя.

## Дополнительные воспроизведения

[probe_cases.py](probe_cases.py) создаёт входные файлы во временном каталоге, вызывает реальное ядро, views и CLI и сохраняет результаты. В конце [probes.json](validation/probes.json) поле `confirmed` содержит `true` для R01–R10. Здесь `true` означает, что дефект воспроизводится, а не что проверяемое поведение корректно.

```powershell
& $reviewPython __dev/review/probe_cases.py
```

Для дополнительного воспроизведения Python AST fallback можно указать интерпретатор без грамматик:

```powershell
$env:GCB_REVIEW_FALLBACK_PYTHON = 'C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $reviewPython __dev/review/probe_cases.py
Remove-Item Env:/GCB_REVIEW_FALLBACK_PYTHON
```

Скрипт не удаляет пакеты. Все тестовые исходники создаются и удаляются через `TemporaryDirectory`. Для проверки смешивания версий он меняет только временный файл. Счётчик разборов временно оборачивает `TSBackend.root` и восстанавливает метод в `finally`; сами ответы не подменяются.

Контрольные примеры с однострочной Python-функцией, Bash-функцией и YAML block scalar дали согласованные ответы и в список дефектов не включены.

## Границы покрытия

Полный сплошной sweep всех строк всех фикстур не завершён. Нет проверок всех поддерживаемых версий Python, Linux/macOS, внешних реальных проектов или производительности на эталонном оборудовании. Нет построчного аудита каждого вспомогательного инструмента. Эти результаты относятся к ядру и перечисленным интеграциям в текущем checkout.

Старый `test/test__replace_in_files.py` не запускался: проект прямо предупреждает, что при ошибках он удаляет фикстуры. Наличие этих файлов в читающем sweep не означает запуск изменяющих их тестов. Не выполнялись генерация новых эталонов, `--record`, исправления production-кода, коммиты, deploy или разрезание пользовательских исходников.
