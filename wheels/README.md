# GLSL wheels — Plan10, 2026-11-01

**Основное колесо принято по Plan11 D1.** Повторная приёмка после установки в
эталонный Python 3.12.10 / tree-sitter 0.26.0: **480/480**. В tools точки tree-sitter
читаются только через `[0]`/`[1]`: getters runtime 0.26.0 повреждают ссылки.
Подробности и исторические результаты: `../__dev/review/GLSL_BUILD.md`.
Поставляется только capsule1; диагностические варианты сохранены в manifest и
в сборочной папке на T:, строки ниже — историческая provenance.

Все колёса: CPython stable ABI `cp310-abi3`, Windows x64 `win_amd64`, Python >=3.10.
Фактические прогоны выполнены только на Python 3.12.10 Windows x64; Hermes и другие
версии Python не проверялись.

| Wheel | Источник / commit | ABI | SHA256 wheel |
|---|---|---:|---|
| tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-win_amd64.whl | https://github.com/Caellian/tree-sitter-glsl / 3a00d49a88cb53eec519b49d8e234e77d916f8ac | 15 | 6c18b83d121fa32da65c45e86c670d53e9ad4bf8793cbc59235d924c8193ba2a |
| tree_sitter_glsl_spec-1.0.0+regen15-cp310-abi3-win_amd64.whl | тот же commit; CLI 0.27.1 generate --abi 15 | 15 | 8d661660b2d7fc06b8f2886fced0471c0941448bff9b7217828a142bab65d07d |
| tree_sitter_glsl_spec-1.0.0+regen14-cp310-abi3-win_amd64.whl | тот же commit; CLI 0.27.1 generate --abi 14 | 14 | e5746ffee7ec4ae2230d6fe715d293aa3b1119f640393a3ff03844207163ea5d |
| tree_sitter_glsl-0.2.0+capsule1-cp310-abi3-win_amd64.whl | https://github.com/tree-sitter-grammars/tree-sitter-glsl / e47b8b62b59d0e3529f1c31b03e025d6bd475044 (v0.2.0) | 14 | 5f9c3874f95655b1c9d52c268c6f2ca04aa7c4f54b265543007b39b8cfbe0892 |

`build_manifest.json` содержит SHA256 parser.c, grammar.js, binding.c, версии сборочных
зависимостей и метаданные всех вариантов. `capsule1.patch` — полный diff основного wheel:
PyLong → PyCapsule, локальная версия, согласованные cp310/Py_LIMITED_API=0x030A0000.
parser.c и grammar.js в основном варианте не менялись. Лицензии исходных проектов
включены в wheels.

## Повтор основной сборки

Сборочная папка: `T:/AgentsWork/glsl-wheel-plan10`; исходники и все промежуточные данные
остаются там. C: используется только для чтения установленного MSVC/Windows SDK.
Сохранённый `build-wheel.cmd` — фактически использованная команда сборки после подготовки
исходников. Следующие команды предназначены для **новой** папки (не запускать поверх
существующей сборки). Выполнять из PowerShell:

```powershell
$work = 'T:\AgentsWork\glsl-wheel-plan10-rebuild'
$tools = 'T:\AgentsWork\ProjectStarter\__HQ\tools'
$py = 'T:\AgentsWork\venv\Scripts\python.exe'
New-Item -ItemType Directory -Path "$work\tmp","$work\pip-cache","$work\build-deps" -Force
$env:TEMP = "$work\tmp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = "$work\pip-cache"
$env:PYTHONDONTWRITEBYTECODE = '1'
git clone --no-checkout https://github.com/Caellian/tree-sitter-glsl.git "$work\source"
git -C "$work\source" fetch origin 3a00d49a88cb53eec519b49d8e234e77d916f8ac
git -C "$work\source" checkout --detach 3a00d49a88cb53eec519b49d8e234e77d916f8ac
git -C "$work\source" apply "$tools\wheels\capsule1.patch"
& $py -m pip install --target "$work\build-deps" --no-deps setuptools==84.2.1 wheel==0.48.0 build==1.6.1 packaging==26.3 pyproject-hooks==1.3.3 colorama==0.4.6
$env:PYTHONPATH = "$work\build-deps"
```

Далее в том же окружении через `cmd.exe /d` выполнить (подставить новый work):

```bat
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
cd /d T:\AgentsWork\glsl-wheel-plan10-rebuild\source
T:\AgentsWork\venv\Scripts\python.exe -m build --wheel --no-isolation --outdir T:\AgentsWork\glsl-wheel-plan10-rebuild\dist
```

Версия генератора исходного parser.c в его шапке не указана. package-lock.json
коммита фиксирует CLI 0.26.8. Мы не утверждаем, что именно им получен исходный parser.c;
проверенная регенерация CLI 0.27.1 / ABI 15 дала побайтно тот же parser.c.

## Проверка и установка

Установка в выбранный Python (путь к tools подставить свой). В эталонный venv это
колесо уже установлено; Hermes не менялся:

```powershell
<python> -m pip install --force-reinstall --no-deps <tools>/wheels/tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-win_amd64.whl
```

Готового колеса для Linux/macOS/Windows ARM нет: соберите из закреплённого исходника
с capsule1.patch по процедуре выше, выбрав свой компилятор и тег платформы. Не используйте
upstream 1.0.0 вместо capsule1 на tree-sitter 0.26.0.

Историческая установка основного wheel в отдельную тестовую папку:

```powershell
$env:TEMP = 'T:\AgentsWork\glsl-wheel-plan10\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'T:\AgentsWork\glsl-wheel-plan10\pip-cache'
$env:PYTHONDONTWRITEBYTECODE = '1'
T:\AgentsWork\venv\Scripts\python.exe -m pip install --target T:\AgentsWork\glsl-wheel-plan10\glsl-test --no-deps 'T:\AgentsWork\ProjectStarter\__HQ\tools\wheels\tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-win_amd64.whl'
```

Для замены в другом выбранном окружении синтаксис —
`<python> -m pip install --force-reinstall --no-deps <точный путь wheel>`.
Основное колесо принято по Plan11 D1; устанавливать выбранным Python этой командой. Команды приёмки, варианты
и минимальный повтор приведены в GLSL_BUILD.md.
