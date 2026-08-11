# HowTo: тестирование get_codeblock (golden)

Запускать из корня `tools/`. Входы — фикстуры в `test/` (см. `test/README.md`).
Метод: прогнать команды, записать вывод в эталонный файл, сверить руками (оракул — палец,
не автор кода). Ставим эталоны ДО правок парсинга.

## Команды (пути к фикстурам)

### Python — `test/pythonSRC/backends/`
```bash
# outline: скелет def/class всего файла (H = именованные, if/for не в счёт)
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --outline
py get_codeblock.py --file test/pythonSRC/backends/resolve.py   --outline
# outline с ограничением глубины
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --outline --level 1
# лестница вложенности в глубокой точке (chat: ожидаем уровни 4→1)
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --line 140
# лестница на строке ре-экспорта (модульный уровень → 1)
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --line 51
# --query: блок в обрамлении якорей (#Block level.. / #Block end..)
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --line 140 --query
py get_codeblock.py --file test/pythonSRC/backends/__init__.py --line 140 --level 1 --query
```

### Markdown — `test/mdSRC/` (карточки)
```bash
# outline = оглавление карточки (H1 файл → H2 секции → H3/H4)
py get_codeblock.py --file test/mdSRC/capture.py.md --outline
py get_codeblock.py --file test/mdSRC/capture.py.md --outline --level 2
# вытащить раздел по строке из outline (## Public API у capture — строка 4)
py get_codeblock.py --file test/mdSRC/capture.py.md --line 4 --query
py get_codeblock.py --file test/mdSRC/cli.py.md --line 1
```

### TypeScript — `test/tsSRC/src/`  ·  C# — `test/csharpSRC/`
```bash
# --line/ладдер/--query работают сейчас; --outline для TS/C# — ПОКА не реализован
py get_codeblock.py --file test/tsSRC/src/analyzer.ts --line 41
py get_codeblock.py --file test/tsSRC/src/analyzer.ts --line 41 --query
py get_codeblock.py --file test/csharpSRC/GlobalStopWatchInstance.cs --line 12
py get_codeblock.py --file test/csharpSRC/GlobalStopWatchInstance.cs --line 12 --query
```

## Что сверять пальцем (оракул)
- **уровни**: `level = 1 + объемлющие тела`; корень = 1; `0` глубиной НЕ бывает; заголовок блока
  на уровне родителя, тело — на 1 глубже; в MD `level = глубина заголовка` (без +1).
- **лестница**: строки от внутреннего блока к внешнему; ренджи вложены.
- **outline**: только именованные (def/class · заголовки MD), ренджи соседей НЕ перекрываются.
- **--query**: тело байт-в-байт между `#Block level: N range: X-Y` и `#Block end: E`.

## Формат вывода
- метадата (без `--query`) — лестница, по строке `<prefix>Block level: N range: X-Y`;
- `--outline` — то же + метка: `<prefix>Block level: N range: X-Y — <label>`;
- `--query` — заголовок, тело байт-в-байт, футер `<prefix>Block end: E`;
- префикс: `#` Python/Markdown, `//` TS/C#.

## Аргументы
| Флаг | Смысл |
|------|-------|
| `--file PATH` | файл (код или `.md`) |
| `--line N` | строка (1-based) — для ладдера/`--query` |
| `--level L` | c `--line`: адрес блока (0=текущий, -N=родители, +N=от верха); c `--outline`: предел глубины |
| `--query` | вернуть текст блока (в обрамлении) вместо лестницы |
| `--outline` | оглавление структуры (без `--line`) |
| `--project-root PATH` | корень для относительных путей |

## Известные баги под будущие эталоны
- `find_body_end` растягивает конец блока на мультилайн-сигнатурах (задевает `--query`/`get_blocks`) — чинить под golden.
- `--outline` для TS/C# — реализовать под этими же эталонами.
