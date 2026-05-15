# Majestic RP Proton Linux Patch

Универсальный патч и запускалка для **Majestic RP / Majestic Launcher** под Linux через **Steam Proton** и **GTA V Legacy**. Помогает запускать Majestic RP на Ubuntu, Fedora, Arch, Manjaro, Linux Mint и других Linux-системах без ручного редактирования Proton prefix.

Пак специально подготовлен для комфортной игры на **server LAS VEGAS** семьи Moretti - [Moretti Club](https://moretti.club/). При этом технически он остается универсальным Proton-патчем для Majestic Launcher под Linux и может работать с другими серверами Majestic.

## Зачем это нужно

Majestic Launcher изначально рассчитан на Windows. Под Linux через Proton часть путей, worker-файлов Electron и launch config может работать иначе: `app.asar`, `gamePatcher.js`, Wine drive, `compatdata`, Rockstar Launcher и GTA V должны совпасть в правильной связке.

Этот пак автоматизирует весь набор действий:

- находит Steam и GTA V;
- определяет настоящий AppID игры через Steam manifest;
- находит нужный Proton prefix;
- патчит Majestic Launcher;
- настраивает GTA V для запуска через Proton;
- запускает лаунчер одной командой.

## Какие проблемы решает

Пак полезен, если ты ищешь, как запустить **Majestic RP на Linux**, **Majestic Launcher через Proton** или **GTA V Legacy с Majestic под Steam Proton**.

Он закрывает типичные проблемы запуска:

- Majestic Launcher не видит GTA V под Linux.
- Majestic Launcher запускается, но patcher не стартует из `app.asar`.
- `gamePatcher.js` не работает корректно внутри Electron `app.asar`.
- Нативный patcher получает Linux/Wine путь вместо понятного Wine drive.
- GTA V запускается не через нужный Rockstar Launcher flow.
- Включается debug mode, из-за чего сервер может отклонить подключение.
- CEF/GPU внутри Majestic Multiplayer работает нестабильно под Proton.
- Нужно быстро настроить Majestic RP для Ubuntu, Fedora, Arch или Steam Deck-подобной Linux-среды.

## Что поддерживается

Дистрибутивы:

- Ubuntu / Debian / Linux Mint
- Fedora
- Arch / Manjaro
- другие Linux-системы со Steam и Proton
- Steam Deck / SteamOS-подобные окружения, если есть доступ к desktop mode и файлам Steam

Установки Steam:

- обычный Steam
- Flatpak Steam
- Snap Steam
- нестандартные Steam libraries

Если у пользователя ручной Proton prefix, Lutris, Bottles или другая нестандартная схема, пути можно указать вручную в `majestic-proton.conf`.

## Быстрый старт

Положи файлы рядом с `Majestic Launcher.exe`:

```text
install-and-run-majestic-proton.sh
majestic-proton.conf
majestic-proton-js-patcher.js
```

Запусти:

```bash
chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh
```

Если нужно поменять разрешение игры:

```bash
GAME_WIDTH=1280
GAME_HEIGHT=720
```

Эти параметры находятся в `majestic-proton.conf`.

## Moretti Club / server LAS VEGAS

Этот пак продвигает игру на **Server LAS VEGAS** семьи Moretti:

[Moretti Club](https://moretti.club/)

Если ты пришел играть на Moretti LAS VEGAS с Linux, этот набор файлов должен быстро подготовить Majestic Launcher и GTA V Legacy под Proton. При этом скрипт не привязан жестко к одному серверу и может использоваться как общий Majestic RP Linux patch.

## Что делает скрипт

- Ищет Steam в стандартных, Flatpak и Snap путях.
- Сканирует Steam library folders.
- Находит GTA V Legacy по `GTA5.exe` и `x64j.rpf`.
- Читает `appid` из `appmanifest_*.acf`.
- Находит соответствующий `steamapps/compatdata/<appid>`.
- Находит установленный Proton.
- Находит `Majestic Launcher.exe`.
- Создает Wine drive, например `G:\`, который указывает на папку GTA V.
- Создает или обновляет `commandline.txt`.
- Правит `settings.xml`, если файл уже создан Rockstar/GTA.
- Отключает debug mode и CEF GPU в конфиге Majestic.
- Распаковывает и патчит `app.asar`.
- Копирует `gamePatcher.js` в `app.asar.unpacked`.
- Запускает Majestic Launcher через Proton.

## Что патчится внутри Majestic

Патч применяется через `majestic-proton-js-patcher.js`.

Он делает две ключевые правки:

- `index.js` начинает запускать `gamePatcher.js` из `resources/app.asar.unpacked/dist/electron/main/`.
- `gamePatcher.js` адаптирует launch config под Proton перед вызовом нативного patcher.

Launch config приводится к Proton-friendly виду:

```text
gtaPath = G:\
gtaPlatform = rgl
debug = false
cefUseHardwareAcceleration = false
```

## Файлы проекта

```text
README.md
MAJESTIC-PROTON-PATCH-README.md
package.json
install-and-run-majestic-proton.sh
majestic-proton.conf
majestic-proton-js-patcher.js
```

## Настройка

Обычно ничего трогать не нужно. `APP_ID` лучше оставить пустым: скрипт сам найдет GTA V, прочитает Steam manifest и возьмет правильный AppID.

```bash
APP_ID=
GAME_WIDTH=1280
GAME_HEIGHT=720
GAME_WINDOWED=1
GAME_BORDERLESS=1
MAJESTIC_PLATFORM=rgl
GTA_WINE_DRIVE=g
```

Если авто-поиск не сработал, можно указать пути вручную:

```bash
STEAM_ROOT=
STEAM_COMPAT_DATA_PATH=
GTA_PATH=
PROTON_PATH=
MAJESTIC_EXE=
```

## Зависимости

Базовые команды:

```bash
node
perl
sed
find
```

Для полного патча `app.asar` нужна утилита `asar`:

```bash
npm install -g @electron/asar
```

Ubuntu / Debian:

```bash
sudo apt install nodejs npm perl sed findutils
sudo npm install -g @electron/asar
```

Fedora:

```bash
sudo dnf install nodejs npm perl sed findutils
sudo npm install -g @electron/asar
```

Arch / Manjaro:

```bash
sudo pacman -S nodejs npm perl sed findutils
sudo npm install -g @electron/asar
```

## Проверка проекта

```bash
npm run check
```

Команда проверяет shell-скрипт и JS-патчер:

```text
bash -n install-and-run-majestic-proton.sh
node --check majestic-proton-js-patcher.js
```

## Для поиска

Majestic RP Linux, Majestic Launcher Linux, Majestic RP Proton, Majestic RP Ubuntu, Majestic RP Fedora, Majestic RP Arch, Majestic RP Steam Deck, Majestic Launcher Proton, Majestic Launcher app.asar, Majestic gamePatcher.js, GTA V Proton, GTA 5 Linux, GTA V Legacy Linux, Grand Theft Auto V Linux, Steam Proton GTA V, Rockstar Launcher Proton, Proton compatdata, Proton prefix, Flatpak Steam GTA V, Snap Steam GTA V, Moretti Club, Moretti LAS VEGAS, server LAS VEGAS.

## Важно

Проект не патчит GTA V exe, multiplayer DLL, anti-cheat, DRM или сетевой протокол. Он автоматизирует только Proton-окружение и JS-совместимость Majestic Launcher под Linux.

Moretti Club: [https://moretti.club/](https://moretti.club/)

## Лицензия

Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.
