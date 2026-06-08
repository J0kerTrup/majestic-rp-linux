# Majestic RP Linux — что было сломано и что исправлено

## Проблема

Из трёх платформ GTA V (`rgl`, `steam`, `egs`) реально работала только `rgl`.

---

## Bug 1 — JS-патчер: legacy-иглы не включали `steam`

**Файл:** `majestic-proton-js-patcher.js`

**Проблема:**

Патчер имеет две пары игл для двух версий минификации Windows-лаунчера.
В обеих legacy-иглах массив платформ не содержал `"steam"`:

```js
// было (строка 298 — legacy findGTA):
["rgl","egs"].includes(JO_ENV_PLATFORM)
// → для steam: false → env-override не применяется → лаунчер не находит GTA V

// было (строка 318 — legacy platform):
["rgl","egs"].includes(JO_FORCED_PLATFORM)
// → для steam: false → платформа не форсируется → лаунчер определяет её сам → ошибка
```

**Исправление:**

```js
// стало (строки 298 и 318):
["steam","rgl","egs"].includes(...)
```

Теперь все 4 иглы (2 legacy + 2 current) содержат все три платформы.

---

## Bug 2 — Авто-поиск GTA V не охватывал Heroic Launcher

**Файл:** `install-and-run-majestic-proton.sh` → `find_gta_path()`

**Проблема:**

`find_gta_path()` искала GTA V только в Steam-манифестах и `steamapps/common/`.
Пользователи EGS и RGL через Heroic Launcher устанавливают GTA V в другие директории.
При отсутствии `GTA_PATH` в конфиге — `die "GTA V Legacy was not found"`.

**Исправление:**

Добавлен блок fallback-кандидатов после Steam-поиска:

```bash
"$HOME/Games/Grand Theft Auto V"
"$HOME/Games/GTA V"
"$HOME/Games/Heroic/Grand Theft Auto V"
"$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic/Games/Grand Theft Auto V"
"$HOME/Games/grand-theft-auto-v"
"$HOME/heroic/Grand Theft Auto V"
```

---

## Bug 3 — EGS GTA V не имеет `GTAVLauncher.exe`

**Файл:** `install-and-run-majestic-proton.sh`

**Проблема:**

EGS-версия GTA V не содержит `GTAVLauncher.exe` (это файл Rockstar Games Launcher).
Лаунчер с `MAJESTIC_PLATFORM=egs` внутри Wine пытается запустить `G:\GTAVLauncher.exe`,
файл не существует → запуск игры падает.

**Исправление:**

Добавлена функция `ensure_gta_launcher_for_egs()`:

```bash
if [[ ! -f "$gta/GTAVLauncher.exe" && -f "$gta/GTA5.exe" ]]; then
    ln -sfn "$gta/GTA5.exe" "$gta/GTAVLauncher.exe"
fi
```

Если платформа `egs` и `GTAVLauncher.exe` отсутствует — создаётся симлинк на `GTA5.exe`.
Wine прозрачно следует за симлинком: при запуске `G:\GTAVLauncher.exe` запускается `GTA5.exe`.
EGS DRM (`EOSSDK-Win64-Shipping.dll`) загружается самой `GTA5.exe` — симлинк ничего не ломает.

---

## Bug 4 — `MAJESTIC_PLATFORM=rgl` хардкодом для всех платформ

**Файл:** `install-and-run-majestic-proton.sh`, `majestic-proton.conf`

**Проблема:**

Конфиг содержал `MAJESTIC_PLATFORM=rgl` без авто-определения.
Steam- и EGS-пользователи должны были знать, что нужно менять это значение вручную.

**Исправление:**

Добавлена функция `detect_gta_platform()` с правильным порядком проверки DLL:

```bash
detect_gta_platform() {
  # EGS: EOSSDK уникален — проверяем первым
  if [[ -f "$gta/EOSSDK-Win64-Shipping.dll" ]]; then printf 'egs\n'; return; fi
  # Steam: steam_api64.dll (GTAVLauncher.exe есть и в Steam — проверяем после EOSSDK)
  if [[ -f "$gta/steam_api64.dll" ]]; then printf 'steam\n'; return; fi
  # RGL: только GTAVLauncher.exe без steam_api64.dll
  if [[ -f "$gta/GTAVLauncher.exe" ]]; then printf 'rgl\n'; return; fi
  printf 'rgl\n'
}
```

Логика авто-коррекции при запуске:

```bash
DETECTED_GTA_PLATFORM="$(detect_gta_platform "$GTA_PATH")"
if [[ "$MAJESTIC_PLATFORM" = "rgl" && "$DETECTED_GTA_PLATFORM" != "rgl" ]]; then
  # Конфиг не трогался пользователем, но платформа другая — применяем авто
  MAJESTIC_PLATFORM="$DETECTED_GTA_PLATFORM"
fi
```

Авто-коррекция срабатывает **только** если конфиг не менялся (`rgl` = дефолт).
Если пользователь явно выставил платформу — она не перезаписывается.

---

## Итоговая таблица

| Платформа | DLL-маркер | Запуск в Wine | Стаб GTAVLauncher |
|-----------|-----------|---------------|-------------------|
| `rgl`     | `GTAVLauncher.exe` (без steam dll) | `G:\GTAVLauncher.exe` | не нужен |
| `steam`   | `steam_api64.dll` | `PlayGTAV.exe` (через Steam) | не нужен |
| `egs`     | `EOSSDK-Win64-Shipping.dll` | `G:\GTAVLauncher.exe` → симлинк на `GTA5.exe` | создаётся автоматически |

---

## Быстрый старт по платформам

```bash
# Steam GTA V (обычно работает без изменений)
MAJESTIC_PLATFORM=steam  # в majestic-proton.conf (или авто-определится)

# RGL GTA V (дефолт, работал всегда)
MAJESTIC_PLATFORM=rgl

# EGS GTA V через Heroic — обязательно указать путь если не в Steam
GTA_PATH=/home/user/Games/Grand\ Theft\ Auto\ V  # в majestic-proton.conf
# MAJESTIC_PLATFORM=egs определится автоматически
```
