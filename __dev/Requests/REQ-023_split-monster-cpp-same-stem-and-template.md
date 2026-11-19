# REQ-023 — split_monster, C++: одно имя списка для `x.h` и `x.cpp`; `template <...>` и комментарий остаются в источнике

## Что видно

Перенос блоков из C++-файла `a.cpp` (939 строк, всё внутри `namespace ns { ... }`) в три новых файла:

```
split_monster.py --file a.cpp --split 81,194 src/twin.h \
  --split 138,156,160,171,183,428 src/twin.cpp --split 572 src/gates.h --out-script move1.py
```

### Ошибка 1: у целей с одним стемом одно имя списка

Цели `src/twin.h` и `src/twin.cpp` получили в скрипте одно имя `TWIN_BLOCKS`:

```
TWIN_BLOCKS = [c01, c02]
...
TWIN_BLOCKS = [c03, c04, c05, c06, c07, c08]
...
monster.write('src/twin.h', TWIN_BLOCKS, TWIN_IMPORTS)
monster.write('src/twin.cpp', TWIN_BLOCKS, TWIN_IMPORTS)
monster.cut('a.cpp', TWIN_BLOCKS + TWIN_BLOCKS + GATES_BLOCKS)
```

Второе присваивание затирает первое. Dry-run: оба файла по «6 блоков, 61 строка», в `cut` 13 блоков вместо 9.
`--apply` записал бы блоки .cpp в обе цели, а блоки .h пропали бы из всех файлов. Предупреждения
нет; заметно только по таблице плана. `*_IMPORTS`, видимо, совпадают так же.

### Ошибка 2: шаблон теряет `template <class T>` и комментарий над ним

```
135 // Comment line one ...
136 // comment line two.
137 template <class T>
138 std::vector<T> make_table(const std::vector<Item>& items) {
...
154 }
```

* `--split 135` (начало блока по `get_codeblock --outline`: `[135-154] template <class T> std::vector<T> make_table`)
  выдаёт ошибку: `--split 135 resolves to [1-939], which overlaps [81-87]`. То же для строк 136 и 137:
  `get_codeblock --line 137 --query` отдаёт `■BLOCK : 1-939`, весь namespace.
* `--split 138` переносит только 138-154. Строки 135-137 (комментарий и `template <class T>`) остаются в источнике и
  «прилипают» к следующему блоку (`template <class T>` перед другой функцией меняет её смысл). Цель получает функцию
  без `template`, и `T` там не определён. `verify` проходит: строки сохранены, всё разбирается.
* То же со вторым шаблоном (`[566-583] template <class T> bool check`). Обычные функции (на 170 и на 182) переносятся вместе с комментарием над ними, как положено.

## Что просим

1. Имя списка блоков и импортов уникально для каждой цели (стем + расширение, например `TWIN_H_BLOCKS` /
   `TWIN_CPP_BLOCKS`), или генератор отказывается с понятной ошибкой при совпадении имён.
2. Блок шаблона в C++ — это весь `template_declaration` вместе с преамбулой-комментарием, как у обычной функции.
   `--split` на любой его строке (комментарий, `template <...>`, заголовок, тело) берёт весь блок с 135 по 154.
   Для `get_codeblock --line` на строке `template <...>` — этот блок, а не весь namespace.
3. По возможности: `verify` предупреждает, если в источнике после переноса остался висящий `template <...>`.

## Проверка

Синтетика: в `namespace ns { }` файл `a.cpp` с шаблоном `template <class T> T f(T x) {...}` под двумя строками
комментария и обычной функцией после него. Цели `x.h` и `x.cpp`.
* Сгенерированный скрипт содержит два разных имени списков, а таблица плана показывает правильное число блоков у каждой цели.
* `--split` на строке комментария, на `template` и на заголовке даёт один и тот же блок; после `--apply` в источнике
  не осталось `template`, а в цели шаблон целый.

## Результат (2026-11-19)

1. Имена списков уникальны: стем, а при совпадении стемов — стем + расширение (`TWIN_H_BLOCKS` /
   `TWIN_CPP_BLOCKS`, так же `_IMPORTS`/`_IMP`/`_APPEND`); стем `SOURCE` тоже получает расширение.
   Совпадение и после этого (`a/x.h`, `b/x.h`) — отказ с ошибкой. `split_monster._target_idents`.
2. `get_codeblock --line` в C++: рунг — весь `template_declaration` (внешний из `template<> template<>`),
   поэтому строка комментария, `template <...>`, заголовок дают один блок, и `--split` берёт его целиком.
   `get_codeblock/reader/address.py` (`_DEF_WRAPPERS`). У `template<> template<class U>` метка в outline —
   `~template_declaration` (как и до правки), диапазон верный.
3. После `--apply` verify пишет `WARNING dangling template: файл:строка`, если строка `template <...>` теперь
   стоит над другим объявлением, чем до переноса (без отката).

Тесты: test_split_monster 79/0 (3 новых), check 169/0, golden 16/16, test_cpp 150/0. Sweep `--check-query` на
C++-файлах с шаблонами — 0 находок и до, и после правки.
