#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Ошибка настройки (строка $LINENO). Исправьте указанную причину и повторите выбранный шаг." >&2' ERR
command -v python3 >/dev/null || { echo "Нужен Python 3.11 или новее." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Нужен Python 3.11 или новее")'


SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}  Majestic RP Steam Deck Assistant (Rockstar Edition)${NC}"
echo -e "${CYAN}====================================================${NC}"

show_menu() {
    echo ""
    echo "Выберите действие:"
    echo "  1) Полная автоматическая настройка (Всё под ключ)"
    echo "  2) Автопоиск GTA V и настройка префикса (токены, реестр, диск G:)"
    echo "  3) Запустить установщик/скачивание Rockstar Launcher (через PortProton)"
    echo "  4) Сконфигурировать runner под Steam Deck (1280x800, RGL)"
    echo "  5) Установить и пропатчить Majestic Launcher"
    echo "  6) Добавить ярлык Majestic RP в игровой режим Steam"
    echo "  7) Запустить Majestic RP прямо сейчас"
    echo "  0) Выход"
    echo ""
    read -rp "Введите номер [0-7]: " choice
}

step_setup_rockstar_prefix() {
    echo -e "${YELLOW}[Шаг] Автопоиск игры и настройка префикса Rockstar...${NC}"
    python3 "$SCRIPT_DIR/scripts/setup_rockstar_prefix.py"
}

step_rgl_download() {
    echo -e "${YELLOW}[Шаг] Запуск Rockstar Launcher Downloader...${NC}"
    if ! command -v flatpak &>/dev/null || ! flatpak info ru.linux_gaming.PortProton &>/dev/null; then
        echo -e "${RED}Ошибка: PortProton не установлен. Установите PortProton из Discover.${NC}"
        return 1
    fi
    echo "Запускаем PortProton с обходом крашей Vulkan (SocialClubVulkanLayer)..."
    export WINEDLLOVERRIDES="vulkan-1=n,b"
    export PW_WINE_USE="WINE_LG_11-1"
    
    RGL_EXE="$HOME/.var/app/ru.linux_gaming.PortProton/data/prefixes/DEFAULT/drive_c/Program Files/Rockstar Games/Launcher/Launcher.exe"
    if [[ -f "$RGL_EXE" ]]; then
        flatpak run ru.linux_gaming.PortProton "$RGL_EXE" &
    else
        echo "Скачиваем инсталлятор Rockstar Launcher..."
        TMP_RGL="/tmp/Rockstar-Games-Launcher.exe"
        curl --fail --location --retry 2 --connect-timeout 15 -o "$TMP_RGL" "https://gamedownloads.rockstargames.com/public/installer/Rockstar-Games-Launcher.exe"
        flatpak run ru.linux_gaming.PortProton "$TMP_RGL" &
    fi
    echo -e "${GREEN}Rockstar Launcher запущен! Авторизуйтесь и поставьте GTA V на скачивание.${NC}"
}

step_configure() {
    echo -e "${YELLOW}[Шаг] Настройка конфигурации ~/.config/majestic-runner/majestic-runner.conf...${NC}"
    python3 "$SCRIPT_DIR/scripts/setup_rockstar_prefix.py" --configure

}

step_install_majestic() {
    echo -e "${YELLOW}[Шаг] Установка и патчинг Majestic Launcher...${NC}"
    "$REPO_ROOT/install-and-run-majestic-proton.sh" install
    echo -e "${GREEN}Установка и патчинг лаунчера завершены!${NC}"
}

step_add_to_steam() {
    echo -e "${YELLOW}[Шаг] Добавление Majestic RP в Steam...${NC}"
    if pgrep -x steam >/dev/null; then
        echo "Закройте Steam и повторите пункт 6: Steam может перезаписать ярлык при выходе."
        return 1
    fi
    python3 "$SCRIPT_DIR/scripts/add_steam_shortcut.py"

    echo -e "${GREEN}Ярлык Majestic RP успешно добавлен в Steam Game Mode!${NC}"
}

check_deck_swap() {
    local swap_kb
    swap_kb=$(awk '/SwapTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)
    if [[ "$swap_kb" -lt 15000000 ]]; then
        echo -e "\n${YELLOW}[Совет по стабильности Steam Deck]${NC}"
        echo "Файл подкачки (Swap) сейчас меньше 16 ГБ."
        echo "Чтобы GTA V не вылетала от нехватки памяти (OOM) в людных местах города,"
        echo "рекомендуется расширить Swap до 16 ГБ и настроить swappiness=1:"
        echo "  sudo swapoff /home/swapfile && sudo rm -f /home/swapfile && sudo mkswap --file /home/swapfile --size 16G && sudo swapon /home/swapfile && sudo sysctl -w vm.swappiness=1"
    else
        echo -e "${GREEN}[+] Файл подкачки (Swap) оптимален: >= 16 ГБ.${NC}"
    fi
}

if [[ $# -gt 0 ]]; then
    choice="$1"
else
    show_menu
fi

case "$choice" in
    1)
        step_configure
        step_install_majestic
        step_setup_rockstar_prefix
        if pgrep -x steam >/dev/null; then
            echo "Установка готова. Для добавления ярлыка закройте Steam и выберите пункт 6."
        else
            step_add_to_steam
        fi
        check_deck_swap
        echo -e "\n${GREEN}====================================================================${NC}"
        echo -e "${GREEN}Настройка завершена. Проверьте ярлык Steam и запуск игры.${NC}"
        echo -e "${GREEN}====================================================================${NC}"
        ;;
    2) step_setup_rockstar_prefix ;;
    3) step_rgl_download ;;
    4) step_configure ;;
    5) step_install_majestic ;;
    6) step_add_to_steam ;;
    7) "$SCRIPT_DIR/start-majestic-deck.sh" ;;
    0) exit 0 ;;
    *) echo "Неверный выбор"; exit 1 ;;
esac
