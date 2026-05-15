# Короткая инструкция

Majestic Proton Patch помогает запускать **Majestic Launcher / Majestic RP** на Linux через Steam Proton.

Пак специально подготовлен для комфортной игры на **server LAS VEGAS** семьи Moretti - [Moretti Club](https://moretti.club/). При этом он остается универсальным Proton-патчем для Majestic Launcher и может работать с другими серверами Majestic.

Подходит для запросов: Majestic RP Linux, Majestic Launcher Proton, GTA V Proton, GTA 5 Linux, Moretti LAS VEGAS, server LAS VEGAS.

## Быстрый запуск

Положи рядом с `Majestic Launcher.exe`:

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

## Настройка разрешения

Открой `majestic-proton.conf`:

```bash
GAME_WIDTH=1280
GAME_HEIGHT=720
```

## Что произойдет автоматически

- Будет найден Steam.
- Будет найдена GTA V Legacy.
- AppID будет взят из Steam manifest.
- Будет найден правильный Proton prefix.
- Будет найден Proton.
- Будет найден `Majestic Launcher.exe`.
- Будет создан Wine drive `G:`.
- Будет обновлен `commandline.txt`.
- Будет применен JS-патч к Majestic Launcher.
- Лаунчер запустится через Proton.

## Если авто-поиск не сработал

Укажи пути вручную в `majestic-proton.conf`:

```bash
STEAM_ROOT=
STEAM_COMPAT_DATA_PATH=
GTA_PATH=
PROTON_PATH=
MAJESTIC_EXE=
```

`APP_ID` обычно оставляют пустым:

```bash
APP_ID=
```

## Зависимости

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

## Ограничение

Патч не изменяет GTA V, DLL, anti-cheat, DRM или сетевой протокол. Он только настраивает Proton-окружение и JS-совместимость Majestic Launcher под Linux.

## Лицензия

MIT. Подробности в файле `LICENSE`.
