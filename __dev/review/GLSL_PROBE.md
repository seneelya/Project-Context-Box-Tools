# Проверка GLSL-грамматик — 2026-11-01

> JSON прогонов (эталон `glsl_probe_results_runtime25_2026-11-01.json`, `glsl_integration_results.json` и прочие) — вне репо, в `T:/AgentsWork/glsl-wheel-plan10/review-archive/`: в них текст личных шейдеров владелицы. Фикстура `cloud-layer-main.fs` заменена синтетической `preproc-split.fs`.

Цель: проверить пригодность для get_codeblock на 22 исходных `.fs`/`.vs` из
`Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders`. Исходники шейдеров,
production-код get_codeblock и его зависимости в requirements не изменены.

## Результат

| Грамматика | Чистый разбор файлов | ERROR / MISSING | Функций |
|---|---:|---:|---:|
| tree-sitter-glsl-spec 1.0.0 | 18/22 | 10 | 348 |
| tree-sitter-glsl 0.2.0 | 16/22 | 51 | 348 |

Эта таблица получена на изолированном tree-sitter **0.25.2**, Python 3.12 Windows x64.
Все 348 диапазонов функций обеих грамматик совпали с независимой эвристикой:
сигнатуры в тексте + баланс фигурных скобок после маскирования комментариев.
Это проверка данных целевого набора, не общий GLSL-парсер и не доказательство
корректности всех внутренних блоков.

В cover-map.fs найдены 25 функций (первые — 7–11, 12–21, 22–31),
main 182–256; видны также однострочные функции, 28 глобальных declaration-узлов,
uniform/in/out/const, макросы, #version, #ifdef, циклы и условные операторы.
В sim-step.fs разбираются layout(location=...) и выходные переменные.

## Ограничения

1. **Совместимость Python-привязки.** В обоих опубликованных Windows wheels
   `language()` возвращает int-указатель. Наш tree-sitter 0.26.0 при прямом
   `Language(module.language())` выдаёт OverflowError. Диагностический мост через
   PyCapsule позволяет загрузить язык, но при подробном обходе наблюдались
   повреждённые координаты и нативные падения 0xC0000005. Причина этих падений
   не локализована до конкретного компонента. На 0.25.2 прямой вызов работает,
   все 44 изолированных разбора завершились успешно. Рабочий runtime НЕ понижен.
   `glsl_probe_results_runtime26_diagnostic.json` — только диагностика: его
   координаты и полноту нельзя считать достоверными.
2. **Препроцессор внутри if/else.** У glsl-spec ошибки в cover-map.fs и color-map.fs
   (MISSING #endif), cloud-layer.fs и cloud-near.fs (ERROR и MISSING в хвосте main).
   Пример: cover-map.fs 195–201 — `#ifdef ... if (...) {...} else #endif {...}`.
   Диапазон main сохраняется, но точность вложенных контейнеров не гарантирована.
   Старая грамматика дополнительно ошибается на #undef и некоторых выражениях.
3. **Недостаточно одной таблицы LangSpec.** У glsl-spec тело функции является
   прямым compound_statement без стандартного поля body; внутри него лежит
   statement_list. Имена параметров и переменных представлены через
   declarator_list/declarator и поля name. Обычный TSNode сворачивает внутренние
   операторы в одну полосу statement_list. Нужны языковые адаптация дерева/Spec
   и извлечение имён, включая несколько declarator в одном declaration.
4. **Реальная проба Classifier.** glsl_adapter_probe.py использует существующие
   LangSpec, TreeSitterSpec и Classifier с временным FlatNode, раскрывающим
   statement_list. Без него первая функция содержит одну полосу 8–10, с ним —
   expression_statement 8–9 и return_statement 10. Карта сохранена в
   glsl_adapter_outline.txt (вне репо, в архиве). Это эксперимент, НЕ зарегистрированный профиль;
   #define пока захватывает начало следующей строки, подписи объявлений ещё
   не перечисляют имена. Полный sweep инвариантов и проверка --name/--query
   на интегрированном профиле НЕ выполнены.

## Вывод для get_codeblock

**glsl-spec подходит как основа**, лучше старой грамматики на этом наборе.
Для карты функций и извлечения функций целиком результат обнадёживающий.
Для полноценной адресации вложенных блоков по CONTRACT пока не готова:
сначала решить совместимость runtime, нормализацию дерева и поведение на
ошибках препроцессора. Готовый профиль нельзя объявить принятым лишь по числу
распознанных функций. Нельзя скрывать ERROR/MISSING или выбирать одну ветку
препроцессора с потерей остальных строк.

## Воспроизведение

Из корня tools, PowerShell:

```powershell
$py = 'T:/AgentsWork/venv/Scripts/python.exe'
& $py -m pip install --only-binary=:all: --no-deps tree-sitter-glsl-spec==1.0.0 tree-sitter-glsl==0.2.0
& $py -m pip install --target "$env:TEMP/projectstarter-glsl-runtime25" --only-binary=:all: --no-deps tree-sitter==0.25.2
& $py -u __dev/review/glsl_probe.py --runtime25
& $py __dev/review/glsl_adapter_probe.py
# Диагностика рабочего runtime (возможны падения дочерних процессов):
& $py -u __dev/review/glsl_probe.py
```

Каждый файл разбирается отдельным дочерним процессом; падения не обрывают весь
прогон. Версии, ошибки, типы узлов, сигнатуры, диапазоны и независимый oracle —
в glsl_probe_results_runtime25.json. Обе грамматики установлены в рабочий venv;
отдельная копия runtime 0.25.2 находится в TEMP, рабочий остаётся 0.26.0.
