# test/parity — эталон старых хендлеров (для миграции на reader/IR)

Золотой слепок вывода **старых** языковых хендлеров (`get_codeblock.handlers`) по всем
фикстурам `test/` (кроме `secret/`): `outline` + `line_level` (каждая строка) + `get_blocks`
(лестница на каждую строку) + `declarations`.

Зачем: когда `outline`/`ladder`/`line_level` будут переезжать с делегации на IR (Vision03,
шаг «полный функционал на новом backend»), этот слепок — эталон паритета. Адресация
(`get_blocks`/`line_level`) обязана совпасть побайтово (от неё зависят внешний
`get_codeblock()` и `--line`); формат `outline` может стать новым (unified `.0`-at-depth).

## Файлы
- `golden_capture.py` — генератор слепка (путь к tools выводится из своего расположения).
- `golden_old.txt` — сам слепок (сгенерирован; регенерировать при изменении фикстур/хендлеров).

## Перегенерация
```
python test/parity/golden_capture.py > test/parity/golden_old.txt
```
