# Majestic RP Proton Linux Patch

Универсальный набор скриптов для запуска Majestic RP на Linux через Steam Proton и GTA V Legacy. Автоматизирует поиск Steam, GTA V, Proton prefix, патчинг app.asar и запуск лаунчера одной командой.

`Discord для поддержки:` https://discord.gg/fkNExq39Yg

## Что делает скрипт

- Находит Steam, GTA V Legacy и нужный Proton prefix
- Создаёт Wine drive (например G:\), указывающий на папку GTA V
- Патчит app.asar — инжектирует хуки в index.js для корректной работы нативного patcher'а под Proton
- Настраивает commandline.txt, settings.xml, конфиги Majestic
- Отключает debug mode и CEF GPU
- Запускает Majestic Launcher через Proton

## Требования

- Linux с установленным Steam и Proton (Proton Experimental)
- Купленная GTA V Legacy
- Установленный Majestic Launcher в Proton prefix GTA V
- Node.js, npm, perl, sed, find
- Утилита asar (npm install -g @electron/asar)

## Установка Majestic Launcher через Protontricks
Перед использованием скрипта нужно установить сам Majestic Launcher в тот же Proton prefix, что и GTA V.
1. Скачай установщик Majestic Launcher
Официальный .exe с сайта Majestic RP.
2. Установи через Protontricks
```bash
# Установи protontricks, если ещё нет
# Ubuntu/Debian:
sudo apt install protontricks

# Arch:
sudo pacman -S protontricks

# Fedora:
sudo dnf install protontricks
```
```bash
# Вариант A: через GUI
protontricks --gui
В GUI выбери:
    GTA V (AppID 271590) в списке игр
    Select default prefix
    Run an .exe → укажи скачанный MajesticLauncherSetup.exe
    Пройди стандартный установщик Windows

# Вариант B: через командную строку (AppID GTA V = 271590)
protontricks 271590 /путь/к/MajesticLauncherSetup.exe
```
4. Проверь, что лаунчер установился
После установки файлы должны лежать по пути:
`~/.local/share/Steam/steamapps/compatdata/271590/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/`
Или, если Steam library на другом диске:
`/mnt/games/SteamLibrary/steamapps/compatdata/271590/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/`
Внутри должна быть Majestic Launcher.exe.

## Быстрый старт
1. Клонируй репозиторий
```bash
git clone https://github.com/J0kerTrup/majestic-rp-linux.git
cd majestic-rp-linux
```
2. Скопируй скрипты в папку с Majestic Launcher
```bash
# Пример для стандартного Steam
cp install-and-run-majestic-proton.sh \
   majestic-proton.conf \
   majestic-proton-js-patcher.js \
   ~/.local/share/Steam/steamapps/compatdata/271590/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/

# Пример для Steam на другом диске
cp install-and-run-majestic-proton.sh \
   majestic-proton.conf \
   majestic-proton-js-patcher.js \
   /mnt/games/SteamLibrary/steamapps/compatdata/271590/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/
```
3. Запусти
```bash
cd ~/.local/share/Steam/steamapps/compatdata/271590/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/

chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh
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

## Настройка
Все параметры в `majestic-proton.conf`:
```bash
# Разрешение игры
GAME_WIDTH=3840
GAME_HEIGHT=2160

# Режим окна (1 = windowed/borderless, 0 = fullscreen)
GAME_WINDOWED=1
GAME_BORDERLESS=1

# Платформа запуска (rgl / steam / egs). Для Proton рекомендуется rgl
MAJESTIC_PLATFORM=rgl

# Буква Wine drive для GTA V
GTA_WINE_DRIVE=g

# Proton verb (waitforexitandrun — для запуска из Steam, runinprefix — из терминала)
PROTON_VERB=waitforexitandrun
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

## Лицензия

Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.
