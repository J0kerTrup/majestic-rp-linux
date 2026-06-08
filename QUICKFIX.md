# 🚀 Быстрый гайд для пользователей с ошибкой Rockstar Launcher

## TL;DR — Если Rockstar Launcher просит ключ продукта:

### 1️⃣ **Обновить токен Steam** (2 мин)
```bash
cd ~/.local/share/Steam/steamapps/common/Grand\ Theft\ Auto\ V
wine GTA5.exe
# Подождать загрузку меню → Ctrl+Q для выхода
```

### 2️⃣ **Очистить кеш**
```bash
find ~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata \
  -path "*/Documents/Rockstar Games" -type d -exec mv {} {}.bak \;
```

### 3️⃣ **Обновить скрипты**
- Скопировать **обновленные** файлы:
  - `install-and-run-majestic-proton.sh`
  - `majestic-proton-js-patcher.js`

### 4️⃣ **Запустить**
```bash
./install-and-run-majestic-proton.sh
```

---

## Что было исправлено?

| Проблема | Решение |
|----------|---------|
| `steam_appid.txt` отсутствует | ✅ Скрипт создает в двух местах |
| Steam переменные теряются | ✅ Явный проброс через `env` |
| Неправильный `WINEPREFIX` | ✅ Явная экспортация |

---

## Проверка логов

```bash
tail -20 ~/majestic-rp-linux/logs/majestic-proton.log | grep steam_appid
```

Должно быть:
```
[SUCCESS] [Steam] steam_appid.txt written | file=.../steam_appid.txt appid=271590
```

---

**Полный анализ**: см. `ROCKSTAR_LAUNCHER_FIX.md`
