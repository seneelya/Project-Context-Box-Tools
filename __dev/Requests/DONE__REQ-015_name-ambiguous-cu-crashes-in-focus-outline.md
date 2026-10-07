# REQ-015 — `--name` с двумя точными совпадениями в `.cu` падает в `classify.outline_rows`

## Что нашла

Повтор логов (2026-10-07, сверка `views.py` со старой версией — падают ОБЕ, это не регрессия):

```
cd Y:\SRC\llama.cpp_mix
get_codeblock.py --file ggml/src/ggml-cuda/allreduce.cu --name ggml_cuda_ar_pipeline_init --query
//name: "ggml_cuda_ar_pipeline_init" — ambiguous: 2 exact; pick one with --line N --query
Traceback …
  reader/classify.py, in outline_rows
    _n, glued = _owning_block(spec, parent_scope.children(), target.start_row + 1,
AttributeError: 'NoneType' object has no attribute 'children'
```

Два точных совпадения → `--name` уходит в пакетное оглавление с фокусом на каждой строке
(`--line A,B --outline`), и для одной из них `parent_scope = spec.body(chain[idx - 1])` — `None`:
у родителя цепочки нет тела (вероятно, прототип и определение одной функции; у прототипа тела нет).

## Где

`get_codeblock/reader/classify.py::outline_rows`, ветка `focus_line` — строка с `parent_scope`.

## Чего хочется

Родитель без тела → искать преамбулу в его собственных детях или не клеить вовсе, но не падать;
оглавление пакета показывает обе точки.

## Как проверить

Команда выше отдаёт пакетное оглавление с двумя строками, без трассировки; golden-случай с
`.cu`/`.h`, где функция объявлена и определена в одном файле.

— Соня5 (Claude Opus 5.5), 2026-10-07

## Сделано (2026-10-07)

Родитель цепочки — рамка `#else` без тела. `outline_rows` брал `spec.body(родителя)` → None.
Теперь скоуп считается одним правилом с лесенкой: `classify._scope_inside` (тело, тело рамки или
сама рамка без тела), и фокус-карта проходит им цепочку от корня; тело цели — тем же правилом
(рамка `#else` раскрывается, как в полном оглавлении). Golden `name_ambiguous_else_branch`
(`test/Edge/Edge.else_branch.cu`; без правки падает). Не трогали: функция внутри `#else` в
`allreduce.cu` разбирается tree-sitter'ом не как определение — пакетное оглавление показывает
саму рамку `#else`, а не функцию.
