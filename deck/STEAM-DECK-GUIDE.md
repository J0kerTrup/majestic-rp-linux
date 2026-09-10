# Majestic RP on Steam Deck (Rockstar Games Launcher / Non-Steam Edition)

[Русская версия](#руководство-по-установке-majestic-rp-на-steam-deck-версия-rockstar-games-launcher) | [English Version](#steam-deck-majestic-rp-guide-rockstar-games-launcher-version)

---

## Руководство по установке Majestic RP на Steam Deck (Версия Rockstar Games Launcher)

Это полное руководство по установке и настройке **Majestic RP** на **Steam Deck**, если у вас версия GTA V **не в Steam**, а куплена напрямую в **Rockstar Games Launcher (Social Club)** или используется готовая чистая папка игры.

### Быстрый старт

Нужны установленная GTA V Legacy Rockstar Edition, Steam и Proton. Закройте игру и процессы Wine. Папка игры может называться произвольно; мастер ищет `GTA5.exe` без учёта регистра. Для добавления ярлыка закройте также Steam:

```bash
cd ~/Documents/majestic-rp-linux
./deck-setup.sh 1
```
Скрипт автоматически:
1. Сконфигурирует параметры под экран Steam Deck (1280x800, RGL).
2. Скачает, установит и пропатчит Majestic Launcher под Proton.
3. При пустом назначении и единственном источнике импортирует данные Social Club, создаст симлинки и обновит путь установки в реестре.
4. Удалит конфликтующие ключи Steam из префикса (чтобы не было ошибки 113 `LAUNCHER_ERR_STEAM_FAILED`).
5. Добавит ярлык `Majestic RP`, если Steam закрыт. Иначе предложит закрыть Steam и выполнить пункт 6.

---

### Подробная пошаговая инструкция

#### Шаг 1: Подготовка файлов игры GTA V

У вас есть два пути получить файлы игры на Steam Deck:

* **Вариант А (Скачивание через официальный лаунчер):**
  1. Установите **PortProton** из Discover (Flatpak).
  2. Запустите инсталлятор Rockstar Launcher с обходом крашей Vulkan:
     ```bash
     export WINEDLLOVERRIDES="vulkan-1=n,b"
     export PW_WINE_USE="WINE_LG_11-1"
     flatpak run ru.linux_gaming.PortProton /path/to/Rockstar-Games-Launcher.exe
     ```
  3. Войдите в аккаунт Rockstar и поставьте GTA V на скачивание.
  4. После скачивания закройте Rockstar Launcher. Перемещать игру не нужно: мастер ищет установки PortProton.

* **Вариант Б (Быстрый перенос готовой игры / Репака):**
  * Если у вас уже есть установленная чистая GTA V на ПК или диске, просто скопируйте папку с игрой в:
    `/home/deck/Games/Grand Theft Auto V`

---

#### Шаг 2: Настройка префикса и установка Majestic

1. Перейдите в папку с раннером:
   ```bash
   cd ~/Documents/majestic-rp-linux
   ```
2. Запустите автоматический ассистент:
   ```bash
   ./deck-setup.sh
   ```
3. Выберите пункт **1 (Полная автоматическая настройка)**.
   * Существующие данные Rockstar сохраняются. Импорт из PortProton возможен только при пустом назначении и единственном источнике с `autosignin.dat`; повторный вход всё равно может потребоваться.
   * Скрипт создаст симлинки в `drive_c/Program Files/Rockstar Games/` и диск `G:`.
   * В `system.reg` и `user.reg` будут прописаны пути `Rockstar Games\Grand Theft Auto V`.

---

#### Шаг 3: Запуск в Game Mode (Игровой режим Steam)

1. Ярлык **Majestic RP** уже добавлен в вашу библиотеку Steam.
2. **ВАЖНОЕ ПРАВИЛО:** В свойствах добавленного ярлыка в Steam **НЕ** включайте галочку *«Принудительно использовать определенный инструмент совместимости Steam Play»*.
   * Скрипт `start-majestic-deck.sh` — это нативный Linux-скрипт. Он сам вызывает Proton Experimental внутри себя с правильными переменными окружения.
   * Если принудительно включить Proton в свойствах ярлыка Steam, Steam Game Mode внедрит переменные `SteamAppId 271590`, что сломает лаунчер Rockstar (ошибка `LAUNCHER_ERR_STEAM_FAILED`).
3. Переключитесь в игровой режим (Gaming Mode).
4. Найдите в библиотеке **Majestic RP** и нажмите **«Играть»**.

---

### Решение проблем (Troubleshooting)

#### 1. Ошибка «Не удалось запустить Steam (LAUNCHER_ERR_STEAM_FAILED, code 113)»
* **Причина:** Игра или Rockstar Launcher получили переменную `SteamAppId=271590` либо нашли ключ Steam в реестре префикса и попытались связаться с несуществующей копией игры в Steam.
* **Решение:** Запустите фикс реестра:
  ```bash
  python3 deck/scripts/setup_rockstar_prefix.py
  ```
  И убедитесь, что в Steam в свойствах ярлыка снята галочка «Совместимость».

#### 2. Ошибка «Сервер использует другую версию Majestic»
* **Причина:** Лаунчер автоматически скачал свежую версию клиента с CDN (например, 1.22.0), а игровые серверы проекта в этот момент находятся на утреннем техобслуживании и ещё не обновились.
* **Решение:** Ничего перенастраивать не нужно! Подождите 15–30 минут, пока разработчики завершат обновление серверов, и запустите игру снова.

#### 3. Краш `_wassert (L"!status", L"../dlls/winevulkan/loader.c", 623)`
* **Причина:** Конфликт встроенного оверлея Rockstar `SocialClubVulkanLayer.json` со стандартным WineVulkan.
* **Решение:** Использовать оверрайд `WINEDLLOVERRIDES="vulkan-1=n,b"` (уже зашит в `deck-setup.sh`).

#### 4. CEF: `ERR_CONNECTION_REFUSED`
В предыдущей диагностике сообщалось о loopback-ответах DNS для доменов Majestic. Это наблюдение конкретного запуска, а не подтверждённое объяснение каждого отказа соединения.

Прежнее правило `.net → .com` не подтверждено успешным запуском внутриигрового CEF. Оно больше не добавляется по умолчанию. При настройке удаляется только точная старая сгенерированная строка; остальные параметры сохраняются, исходные файлы копируются в `*.before-deck-setup`. Мастер не меняет системные DNS, IPv6 или `/etc/hosts`.

Если ошибка повторится, нужен свежий лог загрузки `auth.html` и проверка сети в момент ошибки. Автоматического подтверждённого сетевого исправления пока нет.

#### 5. Social Club снова просит вход
Повторная настройка не перезаписывает существующие каталоги Rockstar, даже если `autosignin.dat` отсутствует. Наличие этого файла не доказывает действительность сессии. Импорт не гарантирует отсутствие повторной авторизации.

#### 6. Другой путь, SD-карта и повторная установка
```bash
# Проверки без изменения конфигурации и префикса
python3 deck/scripts/setup_rockstar_prefix.py --check

# Явно выбрать игру для полной установки
GTA_PATH="/run/media/deck/My SD/Моя игра" ./deck-setup.sh 1
```
При нескольких установках мастер предлагает номер или полный путь. При недоступном сохранённом пути он останавливается и просит проверить SD-карту, не выбирая другую игру. Steam-библиотеки берутся из общего детектора раннера; поиск на внешних дисках ограничен стандартными каталогами.

Для отдельного префикса задайте `STEAM_COMPAT_DATA_PATH` — каталог compatdata; Python-мастер также принимает `--prefix` с путём к `pfx`. Пункт 4 сохраняет найденные пути, пункт 5 устанавливает лаунчер, пункт 2 применяет исправления к инициализированному префиксу.

Первая версия изменяемого файла сохраняется рядом с суффиксом `.before-deck-setup`. Восстанавливайте конкретный файл при закрытых Steam/Wine. Каждый файл заменяется целиком через временный файл; установка в целом не является единой транзакцией. После прерывания устраните причину и повторите шаг. Конфликтующие настоящие каталоги и ссылки на другую игру требуют явного разрешения пользователем.

Подробности и проверенные сценарии: [надёжность установщика](SETUP-RELIABILITY.md).

---

## English Version

### Steam Deck Majestic RP Guide (Rockstar Games Launcher Version)

A complete guide to installing and running **Majestic RP** on **Steam Deck** when GTA V is owned via **Rockstar Games Launcher (Social Club)** or when using a standalone GTA V directory.

### Quick Setup

Install GTA V Legacy Rockstar Edition and Proton first. Close Wine and Steam before setup. Arbitrary game folder names are supported; ambiguous discovery asks for a path.

```bash
cd ~/Documents/majestic-rp-linux
./deck-setup.sh 1
```

This will automatically:
1. Configure screen resolution and display settings for Steam Deck (1280x800 borderless, RGL platform).
2. Install and patch the Majestic Launcher for Proton compatibility.
3. Synchronize Social Club authentication tokens, configure dosdevices `G:`, and set Windows registry entries (`InstallFolder="G:"`).
4. Clean conflicting Steam AppID keys from the Proton prefix to avoid `LAUNCHER_ERR_STEAM_FAILED`.
5. Add the shortcut when Steam is closed; otherwise finish this step later with menu option 6.

### Crucial Notes
* **Steam Compatibility Setting:** In Steam shortcut properties, do **NOT** force a Proton compatibility tool. The shortcut executes `start-majestic-deck.sh` natively, which controls Proton internally and sanitizes Steam environment variables.
* **Authentication:** Existing Rockstar directories are preserved. Import only occurs into an empty destination from one unambiguous PortProton source. A saved token does not guarantee a valid session.
* **CEF / DNS:** The previous `.net → .com` workaround is unverified and no longer enabled by default. Setup migrates only its exact generated signature, backing up changed files. No system DNS or hosts changes are made.
* **Custom paths:** Use `GTA_PATH="/path/to/game" ./deck-setup.sh 1`. A missing configured path stops setup instead of silently choosing another installation.
* **Recovery:** Original changed files are saved as `*.before-deck-setup`. Restore only with Steam/Wine closed. File replacements are atomic; the whole setup is not transactional. See [reliability notes](SETUP-RELIABILITY.md).
