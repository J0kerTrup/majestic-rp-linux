# Анализ проблемы Rockstar Launcher на Linux + Исправления

## Выявленные проблемы

### 1. **Отсутствие `steam_appid.txt`** (КРИТИЧЕСКАЯ)
- **Локация**: `install-and-run-majestic-proton.sh` и JavaScript patcher
- **Проблема**: Файл `steam_appid.txt` с содержимым `271590` необходимо создать в двух директориях:
  - В директории GTA V (`$GTA_PATH/steam_appid.txt`)
  - В директории Majestic Launcher (`$MAJESTIC_DIR/steam_appid.txt`)
- **Следствие**: Без этого файла Proton/Wine не может идентифицировать приложение как Steam App ID 271590 (GTA V), и Rockstar Launcher не видит лицензию
- **Решение**: Добавлена функция `write_steam_appid()` в Bash, вызывается перед запуском

### 2. **Потеря переменных окружения при PROTON_VERB=runinprefix**
- **Локация**: Строка 640 в Bash скрипте (`exec "$PROTON" "$PROTON_VERB"...`)
- **Проблема**: При использовании `runinprefix` режима переменные окружения могут не полностью передаваться дочерним процессам
- **Решение**: Используется `env` wrapper для явного проброса всех критических переменных Steam

### 3. **Отсутствие WINEPREFIX в экспортах**
- **Локация**: Строка 619-632 в Bash скрипте
- **Проблема**: `WINEPREFIX` явно не экспортировалась, что может привести к конфликтам при множественных префиксах
- **Решение**: Добавлена явная экспортация `WINEPREFIX="$COMPATDATA/pfx"`

### 4. **JS Patcher не создает steam_appid.txt**
- **Локация**: `majestic-proton-js-patcher.js`, функции `patchWorker()` и прямой патч index.js
- **Проблема**: При инжекции Native Patcher скрипт не создавал `steam_appid.txt` файлы в нужных директориях
- **Решение**: Добавлена функция `writeProtonSteamAppId()` в рабочий процесс (Worker) и прямой патч

---

## Исправленный код

### 1. Bash скрипт (install-and-run-majestic-proton.sh)

**Новая функция (строка ~449):**
```bash
write_steam_appid() {
  local dir="$1"
  local appid="$2"
  local file="$dir/steam_appid.txt"
  log_info "Writing steam_appid.txt for Rockstar Launcher Steam auth" "Steam" "file=$file appid=$appid"
  printf '%s' "$appid" > "$file"
  log_success "steam_appid.txt written" "Steam" "file=$file appid=$appid"
}
```

**Вызов функции (строка ~617):**
```bash
write_commandline
patch_settings_xml "$COMPATDATA/pfx/drive_c/users/steamuser/Documents/Rockstar Games/GTA V/settings.xml"
patch_runtime_configs
reset_rockstar_documents
patch_asar_app

write_steam_appid "$GTA_PATH" "271590"           # GTA V directory
write_steam_appid "$MAJESTIC_DIR" "271590"       # Majestic Launcher directory
```

**Улучшенный запуск Proton (строка ~640):**
```bash
exec env \
  STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_COMPAT_CLIENT_INSTALL_PATH" \
  STEAM_COMPAT_DATA_PATH="$STEAM_COMPAT_DATA_PATH" \
  STEAM_COMPAT_APP_ID="$STEAM_COMPAT_APP_ID" \
  SteamAppId="$SteamAppId" \
  SteamGameId="$SteamGameId" \
  WINEPREFIX="$WINEPREFIX" \
  WINEDLLOVERRIDES="$WINEDLLOVERRIDES" \
  MAJESTIC_PROTON_PLATFORM="$MAJESTIC_PROTON_PLATFORM" \
  MAJESTIC_GTA_WIN_PATH="$MAJESTIC_GTA_WIN_PATH" \
  MAJESTIC_DISABLE_CEF_GPU="$MAJESTIC_DISABLE_CEF_GPU" \
  ELECTRON_DISABLE_SANDBOX="$ELECTRON_DISABLE_SANDBOX" \
  ELECTRON_DISABLE_GPU="$ELECTRON_DISABLE_GPU" \
  "$PROTON" "$PROTON_VERB" "$MAJESTIC_EXE" $MAJESTIC_LAUNCHER_FLAGS
```

**Добавление WINEPREFIX в экспорты (строка ~619):**
```bash
export WINEPREFIX="${WINEPREFIX:-$COMPATDATA/pfx}"
```

### 2. JavaScript Patcher (majestic-proton-js-patcher.js)

**Новая функция в patchWorker (строка ~470):**
```javascript
function writeProtonSteamAppId(basePath) {
  if (!basePath || basePath.startsWith('Z:\\\\')) return false;
  try {
    const appIdPath = path.join(basePath, 'steam_appid.txt');
    fs.writeFileSync(appIdPath, '271590', 'utf8');
    console.log('[LINUX-PROTON DEBUG] wrote steam_appid.txt', { path: appIdPath });
    return true;
  } catch (error) {
    console.log('[LINUX-PROTON DEBUG] failed to write steam_appid.txt', { basePath, error });
    return false;
  }
}
```

**Вызовы в adaptLaunchConfigForProton (строка ~539):**
```javascript
if (config.multiplayerPath && config.configFileName) {
  multiplayerConfigPath = path.join(config.multiplayerPath, config.configFileName);
  patchPermissionCache(config.multiplayerPath);
  writeProtonSteamAppId(config.multiplayerPath);  // Создать steam_appid.txt в папке Majestic
}
if (config.gtaPath) {
  writeProtonSteamAppId(config.gtaPath);          // Создать steam_appid.txt в папке GTA V
}
```

**Прямой патч index.js (строка ~372):**
```javascript
function JO_writeProtonSteamAppId(e){if(!e||e.startsWith("Z:\\\\"))return!1;try{return ue.writeFileSync(ae.join(e,"steam_appid.txt"),"271590","utf8"),P.log("[LINUX-PROTON DEBUG] wrote steam_appid.txt",{path:ae.join(e,"steam_appid.txt")}),!0}catch(e){return P.log("[LINUX-PROTON DEBUG] failed to write steam_appid.txt",{path:e}),!1}}
```

---

## Чек-лист для пользователей (для 3 игроков с ошибкой)

Выполните следующие шаги по порядку **ДО запуска исправленного скрипта**:

### ✅ Шаг 1: Обновить токены Steam
```bash
# Запустить чистую GTA V через Steam до главного меню
cd ~/.local/share/Steam/steamapps/common/Grand\ Theft\ Auto\ V
wine GTA5.exe
# Дождаться загрузки меню, закрыть игру полностью (Ctrl+Q)
```
**Зачем**: Это заставит Steam обновить локальный токен авторизации в префиксе Proton.

### ✅ Шаг 2: Очистить кеш Rockstar Social Club
```bash
# Найти папку Rockstar Documents
find ~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata \
  -path "*/Documents/Rockstar Games" -type d

# Удалить или переименовать папку:
mv "Documents/Rockstar Games" "Documents/Rockstar Games.bak"
```
**Зачем**: Удаляется устаревший кеш лицензий; будет пересоздан при следующем запуске.

### ✅ Шаг 3: Убедиться в наличии файла steam_appid.txt
```bash
# Проверить, что файл существует в Steam префиксе
ls -la ~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/*/pfx/

# Должна быть папка вроде: 271590 (или другой AppID)
```
**Зачем**: Подтверждение, что Proton префикс инициализирован.

### ✅ Шаг 4: Запустить исправленный скрипт
```bash
cd ~/majestic-rp-linux
./install-and-run-majestic-proton.sh
```
**Результат**: При первом запуске скрипт:
1. Создаст `steam_appid.txt` в директориях GTA V и Majestic Launcher
2. Явно пробросит все Steam переменные окружения
3. Запустит Majestic Launcher с полной информацией о лицензии

---

## Что изменилось

| Аспект | До исправления | После исправления |
|--------|---|---|
| `steam_appid.txt` | ❌ Отсутствует | ✅ Создается в GTA V и Majestic DIR |
| Проброс Steam переменных | ⚠️ Потеря при PROTON_VERB | ✅ Явный проброс через `env` |
| `WINEPREFIX` | ⚠️ Неявно | ✅ Явная экспортация |
| Синхронизация Rockstar | ⚠️ Нет гарантии | ✅ `steam_appid.txt` гарантирует идентификацию |
| JS Patcher логика | ❌ Не создает файлы | ✅ Создает при инжекции |

---

## Вероятные причины ошибки у 3 пользователей

1. **Старая/истекшая Steam сессия** в префиксе — исправляется Шагом 1
2. **Отсутствие steam_appid.txt** — исправляется исправленным скриптом
3. **WINEPREFIX указывает на другой префикс** — исправляется явной экспортацией
4. **Кеш Rockstar Games содержит неправильные данные** — исправляется Шагом 2

---

## Тестирование исправления

После запуска исправленного скрипта проверьте логи:
```bash
tail -f ~/majestic-rp-linux/logs/majestic-proton.log | grep -E "steam_appid|STEAM_COMPAT|SteamAppId"
```

Должны быть строки:
```
[TIMESTAMP] [SUCCESS] [Steam] steam_appid.txt written | file=/path/to/GTA_PATH/steam_appid.txt appid=271590
[TIMESTAMP] [SUCCESS] [Steam] steam_appid.txt written | file=/path/to/MAJESTIC_DIR/steam_appid.txt appid=271590
[TIMESTAMP] [DEBUG] [Environment] Exported Proton and Majestic environment | ... SteamAppId=271590 ...
```

---

## Важно ⚠️

- Используйте **исправленные версии обоих файлов**:
  - `install-and-run-majestic-proton.sh`
  - `majestic-proton-js-patcher.js`
- Не смешивайте старую и новую версии
- При обновлении убедитесь, что скрипт имеет права на запись в директории GTA V и Majestic Launcher
