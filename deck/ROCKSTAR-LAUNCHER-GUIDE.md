# Установка и запуск GTA V через Rockstar Games Launcher (Social Club) на Linux / Steam Deck
# Installing and Running GTA V via Rockstar Games Launcher (Social Club) on Linux / Steam Deck

---

## 🇷🇺 Русская версия

Это руководство описывает, как подружить Grand Theft Auto V от Rockstar Games Launcher (Social Club) с **Majestic RP Linux Runner**, избежать конфликтов DRM и настроить префикс Proton.

### Резюме проверенных решений (Что было исправлено)

1. **Конфликт со Steam («Не удалось запустить Steam / LAUNCHER_ERR_STEAM_FAILED, code 113»):**
   * **Проблема:** При запуске игры из Steam (Game Mode) или при наличии ключей `Software\Valve\Steam\Apps\271590` в префиксе, игра пытается инициализировать Steamworks API и падает, так как аккаунт привязан к Social Club, а не Steam.
   * **Решение:**
     * В префиксе Proton удаляются ключи `[Software\Valve\Steam\Apps\271590]`.
     * В скрипте запуска `start-majestic-deck.sh` и раннере очищаются переменные окружения `SteamAppId`, `SteamGameId`, `SteamOverlayGameId`, `SteamClientLaunch`, `SteamEnv`.
     * В ярлыке Steam **не форсируется** Proton Compatibility Tool — запуск идёт как нативный Linux-скрипт, который сам инициирует Proton внутри.

2. **Обход краша Vulkan при загрузке оверлея Social Club (`_wassert` в `winevulkan`):**
   * **Проблема:** Файл `SocialClubVulkanLayer.json` крашит Wine с ошибкой:
     `err:msvcrt:_wassert (L"!status", L"../dlls/winevulkan/loader.c", 623)`
   * **Решение:** Добавить переопределение библиотеки:
     ```bash
     export WINEDLLOVERRIDES="vulkan-1=n,b"
     ```

3. **Синхронизация профиля и авторизации Social Club (без ввода паролей и капчи):**
   * Если вы один раз авторизовались в лаунчере через PortProton или на ПК, файлы сессии можно просто перенести в префикс Proton:
     * `drive_c/users/steamuser/AppData/Local/Rockstar Games`
     * `drive_c/users/steamuser/Documents/Rockstar Games`
   * Скрипт `scripts/setup_rockstar_prefix.py` делает это автоматически.

4. **Регистрация игры в реестре Wine:**
   * Лаунчер Rockstar и Majestic требуют наличия в реестре путей к установленной игре:
     ```reg
     [Software\Rockstar Games\Grand Theft Auto V]
     "InstallFolder"="G:"
     "PatchVersion"="1.0.3889.0"

     [Software\Wow6432Node\Rockstar Games\Grand Theft Auto V]
     "InstallFolder"="G:"
     "PatchVersion"="1.0.3889.0"
     ```
   * Также создаются симлинки в `drive_c/Program Files/Rockstar Games/Grand Theft Auto V` и `Grand Theft Auto V Legacy`.

---

### Быстрая автоматическая настройка

В репозитории подготовлены скрипты, которые делают всё вышеперечисленное автоматически:

```bash
# Автоматическая настройка префикса:
python3 scripts/setup_rockstar_prefix.py

# Добавление ярлыка в Steam Game Mode:
python3 scripts/add_steam_shortcut.py

# Либо интерактивный мастер на Steam Deck:
./deck-setup.sh
```

---

## 🇬🇧 English Version

This guide explains how to configure GTA V from Rockstar Games Launcher (Social Club) with **Majestic RP Linux Runner**, resolve DRM conflicts, and tune the Proton prefix.

### Key Solutions Applied

1. **Steam AppID Collision (`LAUNCHER_ERR_STEAM_FAILED, code 113`):**
   * Occurs when Steam Game Mode injects `SteamAppId=271590` or when old Steam registry keys exist in the Proton prefix.
   * Fixed by sanitizing Steam environment variables in `start-majestic-deck.sh` and removing `Software\Valve\Steam\Apps\271590` registry keys via `scripts/setup_rockstar_prefix.py`.

2. **Vulkan Layer Assertion Crash:**
   * Social Club's Vulkan layer crashes standard WineVulkan loader.
   * Fixed via `WINEDLLOVERRIDES="vulkan-1=n,b"`.

3. **Social Club Seamless Auth Sync:**
   * Login credentials and machine hardware tokens are transferred directly from PortProton's prefix into the Proton prefix via `scripts/setup_rockstar_prefix.py`.

4. **Windows Registry Keys:**
   * The script registers `InstallFolder="G:"` under `Software\Rockstar Games\Grand Theft Auto V` and creates symlinks in `Program Files/Rockstar Games/`.
