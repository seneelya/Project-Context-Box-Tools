# GLSL_LINUX — Plan12, Sol, 2026-11-01

Plan12 выполнен: Linux wheel собран, WSL-приёмка и Windows-регресс завершены.
Ничего не коммитить/деплоить. Все рабочие данные: T:/AgentsWork/glsl-wheel-plan10/plan12.

## Исходник и артефакт

Source 3a00d49a88cb53eec519b49d8e234e77d916f8ac получен git archive из уже скачанного
репозитория; применён неизменённый wheels/capsule1.patch. Версия 1.0.0+capsule1.
SHA256 parser.c `d8759daf83d69862a25417a98807b09b7ac32f15625706b839057e2df3d898e6`,
grammar.js `fd517076cfac59fc52bb07ae45f1495cba2a1d831ad8660ff67c90a43128fbe5`:
побайтно как Windows capsule1. binding.c после git apply имеет CRLF (локальная Git
настройка); его SHA256 a0b465563a58ab9948012d4b4275a3d0a89755944087866dce7a800ed0a61187.
После нормализации CRLF→LF он побайтно равен Windows binding.c (5d9ffb9d…);
никаких иных правок привязки или грамматики нет.

Wheel: `tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl`.
Размер 137863 bytes. SHA256 `55e402505beb13b1f9e91af4d83cc3540d0e71b677d4bc02ca227b57b199cc2b`.
_binding.abi3.so SHA256 `f07cdb7b394461eda738422b9ddb9ef50a8caa0e19012da49bba41255fca0ebc`.
Windows wheel и эталонный Windows venv не менялись.

## Сборка

Официальный quay.io/pypa/manylinux2014_x86_64,
digest sha256:dc58399aca4cfb0de257f92e2de71b4f8421e60cce8542fcd5e28df0c0760942,
размер image inspect **1,704,774,662 bytes**. Образ хранится в Docker storage —
исключение прямо разрешено Plan12. Сборочный Python /opt/python/cp310-cp310/bin/python.
Исходники, build-deps pip --target, build/dist/repaired/tmp/cache/home — bind mount T:.
Полный повторяемый скрипт: wheels/build-linux.sh; запуск и подготовка в wheels/README.md.

```powershell
docker run --rm --mount 'type=bind,source=T:\AgentsWork\glsl-wheel-plan10\plan12,target=/work' --env TMPDIR=/work/tmp --env TEMP=/work/tmp --env TMP=/work/tmp quay.io/pypa/manylinux2014_x86_64@sha256:dc58399aca4cfb0de257f92e2de71b4f8421e60cce8542fcd5e28df0c0760942 bash /work/build-linux.sh
```

Build dependencies: build1.6.1, setuptools84.2.1, wheel0.48.0, packaging26.3,
pyproject_hooks1.3.3, tomli2.5.0 (Python3.10). Все скачаны в plan12/downloads через
Windows pip download; Windows venv не устанавливал/обновлял пакеты.

`auditwheel show` исходного и repaired wheel:

```text
consistent with platform tag: manylinux_2_5_x86_64
external versioned symbols: libc.so.6 {'GLIBC_2.2.5'}
The wheel requires no external shared libraries!
```

`auditwheel repair --plat manylinux_2_17_x86_64` сохранил запрошенный тег и добавил
manylinux_2_5/manylinux1/manylinux2014. Все четыре cp310-abi3 тега проверены внутри
WHEEL. Для поставки заявляем цель плана: Linux x86_64, glibc>=2.17, CPython>=3.10;
практическая приёмка — Ubuntu CPython3.12.3, не все возможные системы.

## WSL: отдельный venv и приёмка

WSL Ubuntu: Python3.12.3, sysconfig.get_platform() реально **linux-x86_64**.
Venv /mnt/t/AgentsWork/glsl-wheel-plan10/plan12/venv, создан --copies на T:.
Ubuntu не имеет ensurepip, а DNS pypi.org из WSL не разрешается. Систему/apt не меняли:
get-pip.py скачан на T: через Windows, Linux wheels тоже скачаны через Windows;
в WSL pip установлен офлайн --no-index --find-links. В venv: tree-sitter0.26.0,
tree-sitter-cpp0.23.4 и точный локальный capsule1 wheel, без зависимостей/ctypes-моста.

| Проверка | Результат |
|---|---|
| language() и Language(capsule) | PyCapsule, ABI15, прямой вызов PASS |
| glsl_wheel_accept.py --index-points | **480/480**, exit0 |
| Состав повтора | 22×20 полных разборов +20 минимальных +20 C++ контролей |
| SHA256 + функции/диапазоны/ошибки/счётчики vs runtime25 | Все совпали |
| test_glsl.py по синтетическим фикстурам | **5 файлов /178 строк /21 функция PASS** |
| test_glsl.py по 22 личным шейдерам (read-only) | **4464 строки /348 функций PASS** |
| D7 из настоящего WSL | Нет модуля → абсолютная команда с Linux wheel; legacy/unsupported/vendored также PASS |
| Windows/Linux outline + --name на исходном cover-map.fs | Равны после нормализации OS mount prefix и CRLF stdout |
| Point.row на Linux | actual refcount delta [0,-1], дефект воспроизводится |
| Point[0] на Linux | [+1,0], корректно |

Сырые JSON/логи с приватными шейдерами — только вне репозитория, в plan12/:
accept-linux.json, accept-workers/, integration-linux.json, accept-linux.log,
cross-output/. В репо не помещались копии/вырезки шейдеров или их текст.

Минимальное обобщение runner: OS-specific корни T:/Y:↔/mnt/t,/mnt/y,
sysconfig platlib, .so/.pyd. Проверки версии, путей/хэшей бинарников, capsule,
таймаута, baseline и число повторов не ослаблены. Default output перенесён в
build-root, чтобы даже запуск без --out не создавал личный JSON внутри репозитория.

## Production и тесты

Production-код изменён только в env_check artifacts: добавлен linux-x86_64.
Тест test_glsl_env.py выбирает native wheel из таблицы, проверяет обе команды
win-amd64/linux-x86_64, неподдержанную платформу linux-aarch64 и vendored copy
без wheels. На Windows и WSL все **6 PASS**. ARM/macOS колесо не собиралось.

## Windows-регресс

check150/0; cardstamp160/0; restamp21/0; golden16/16; cpp150/0; names55/0;
views57/0; GLSL fixture5/178/21; env6PASS. Общий sweep: 152 файла /52083 probes,
CONTAIN=RANGE=OPEN=QUERY=0, известный cp1252 CRASH=71 и LOW LEVEL=5; exit1
честно сохранён, новых HIGH нет. Логи plan12/regression/.

## Документация и ограничения

Обновлены wheels/README.md + build_manifest.json + build-linux.sh, TLDR/README,
CONTEXT_RESTORE и этот отчёт. Нет изменений grammar/parser, Hermes/служб,
Windows пакетов, исходных shader-файлов, коммита или деплоя. Можно переходить
к Plan13; ревью/коммит обоих планов остаются за Claude.
