# LIMbo: Your Intuitive Linux & Docker Navigator
# Might be unfinished in places. Is under long-term development. Use at your own risk.
This project is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) License. See the [LICENSE](LICENSE) file for details.

[English](#english) | [Русский](#русский)

Tired of `htop` and its limited forks? Meet LIMbo – a powerful, intuitive, and highly functional Text User Interface (TUI) for monitoring your Linux system and navigating your Docker environments. Designed for speed and ease of use, LIMbo goes beyond basic monitoring, offering deep insights and seamless directory transitions with minimal keystrokes.

---

<a name="english"></a>

### Why LIMbo?

Traditional TUI monitors like `htop` often fall short on functionality, especially when managing complex Docker setups or frequently jumping between project directories. LIMbo was born out of the need for a more comprehensive and ergonomic tool. My design philosophy prioritizes efficiency: even navigation scripts (`l.sh`, `b.sh`) are named to be single-hand accessible and quickly tab-completed for a fluid workflow.

### Features

#### **System Monitor (Default `lim` command)**

The core `lim` command launches a powerful, interactive TUI system monitor, offering real-time insights into your system's performance and processes.

* **Comprehensive Overview**: Displays CPU, Memory, GPU, Disk I/O, Network I/O, Load Averages, Uptime, and general system information
* **Dynamic Process List**:
    * **Detailed Process Information**: View PID, Username, CPU Usage, Memory Usage (RSS and VMS), and a "smart" display name for processes
    * **Smart Process Naming**: Automatically translates common executable names (e.g., `python3`, `node`, `mysqld`) into more descriptive labels (e.g., "Python Script", "Node.js", "MySQL"). For Java processes, it attempts to extract the JAR name.
    * **Memory Change Indicator**: Easily spot processes with increasing (`+`), decreasing (`-`), or unchanged (`*`) Resident Set Size (RSS) since the last refresh.
    * **Resource Highlighting**: Processes consuming significant CPU or Memory are highlighted for quick identification.
    * **Interactive Sorting**: Sort the process list by various metrics (RSS, CPU, MEM%, PID, VMS, Name) by pressing `Tab` (forward) or `Shift+Tab` (backward). Specific keys (`r`, `c`, `m`, `p`, `v`, `n`) also directly sort by RSS, CPU, Memory, PID, VMS, and Name respectively.
    * **Search/Filter**: (Planned for future, not yet implemented)
* **Interactive Modes**: Toggle specialized views for targeted actions
    * **Docker Mode (`d`)**: Filters the process list to show only Docker container processes
        * **Container Identification**: Clearly shows the associated Docker container name or short ID
        * **Docker Actions (Enter)**: When a Docker process is selected, pressing `Enter` opens a menu to:
            * **Inspect (`i`)**: Run `docker inspect` and display detailed container information in a popup
            * **Restart (`r`)**: Immediately restart the selected Docker container.
            * **Shell (`s`)**: Provides the `docker exec -it <container_id> /bin/bash` command for easy copying to open a shell inside the container.
    * **Killer Mode (`k`)**: Enables a "kill" confirmation menu for selected processes.
        * **Signal Confirmation (Enter)**: When a process is selected, pressing `Enter` brings up a prompt to send `SIGTERM` (`s`) or `SIGKILL (-9)` (`k`).
* **Navigation**: Use `↑`/`↓` for line-by-line navigation, `PgUp`/`PgDn` for page scrolling, and `Home`/`End` to jump to the top/bottom of the list. Mouse click selection is also supported.
* **Help (`h`)**: Access an in-app help screen with keybindings and feature explanations.
* **Refresh (`r`)**: Force a refresh of the Docker cache.

#### **Docker & Bookmark Navigator (`lim tui` or `lim nav`)**

This dedicated TUI allows you to quickly `go` to Docker Compose project directories or custom bookmarked paths.

* **Combined List**: Displays both Docker containers (with their compose path and status) and custom directory bookmarks in a single, sortable list.
* **Quick Navigation (`g` or `Enter`)**: Select an item and press `g` or `Enter` to generate one-time navigation scripts (`l.sh` and `b.sh`) in your *current* directory.
    * **`l.sh`**: A tiny, self-deleting script that `cd`s you into the target directory and launches a new `bash` shell. It informs you how to return to your original directory.
    * **`b.sh`**: Created *inside the target directory*, this script brings you back to your *original* working directory. Both scripts self-delete after a few seconds for cleanliness. This means you can type `./l.sh` (with Tab completion) from anywhere to instantly jump to your project, and `./b.sh` to return.
* **Docker Inspect (`i`)**: Similar to the main monitor, pressing `i` on a Docker entry runs `docker inspect` for detailed information.
* **Bookmark Management**:
    * **Add Bookmark (`a`)**: Interactively add a new bookmark with a name and a target path (defaults to current directory).
    * **Delete Bookmark (`d`)**: Delete the currently selected bookmark.

#### **CLI Commands**

Beyond the TUIs, LIMbo provides a set of powerful command-line utilities for quick tasks, with Bash completion for common arguments.

* `lim inspect <container_id_or_name>` (`lim i`): Displays `docker inspect` output for a given container, with Rich formatting if available.
* `lim go <container_id_or_name>`: Generates `l.sh` and `b.sh` scripts to jump to the Docker Compose directory of a specified container.
* `lim updatecache`: Forces an immediate refresh of the Docker container cache, used by both TUIs and CLI commands. This cache normally updates every 5 minutes via a cron job.
* `lim tp <bookmark_name>`: Jumps to a bookmarked directory, similar to `lim go` but for custom paths.
    * `lim tp add <name> [path]`: Adds a new bookmark. Path defaults to current directory.
    * `lim tp del <name>`: Deletes a bookmark.
    * `lim tp list`: Lists all saved bookmarks in a nicely formatted table.

### Why `l.sh` and `b.sh`?

The idea behind `l.sh` (for **L**aunch) and `b.sh` (for **B**ack) is pure ergonomics. They are intentionally short, one-character names to minimize typing. Combined with Bash tab-completion (`./l.<TAB>`), they offer an unparalleled speed for navigating to deeply nested project directories or Docker Compose folders, far surpassing traditional `cd` commands or complex aliases.

When you use `lim tui` or `lim go`, these scripts are *temporarily* created in your *current* directory. This means you don't need to worry about managing them; they appear when you need them and self-delete shortly after use. The `l.sh` script immediately takes you to the target directory and drops you into a new shell, providing a seamless transition. The `b.sh` script, created in the target directory, lets you return to where you started with the same single-hand, quick-completion convenience.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/srose69/Lim
    cd lim
    ```

2.  **Run the installer**:
    ```bash
    chmod +x install.sh
    sudo ./install.sh
    ```
    The installer will:
    * Update package lists and install core dependencies (`python3`, `pip`, `jq`, `python3-venv`).
    * Install Python libraries (`psutil`, `rich`, `docker`).
    * Check for and install Docker if not present, and add your user to the `docker` group (requires logout/login or `newgrp docker` to take effect).
    * Copy LIMbo scripts to `/usr/lib/lim` and create symlinks (`lim`, `lim_update_cache.py`) in `/usr/local/bin` and `/usr/local/sbin`.
    * Set up a cron job to automatically update the Docker cache every 5 minutes.
    * Install Bash completion for `lim` commands to `/etc/bash_completion.d/`.

    *Note: If you are added to the `docker` group during installation, you will need to log out and log back in, or run `newgrp docker` for the changes to take effect.*

### Usage

* **Start the main monitor**:
    ```bash
    lim
    ```
* **Start the Docker & Bookmark navigator**:
    ```bash
    lim tui
    ```
* **Go to a Docker Compose directory**:
    ```bash
    lim go <container_name_or_id>
    # Then in your current terminal:
    ./l.sh # (and press Tab to auto-complete)
    ```
* **Add a bookmark**:
    ```bash
    lim tp add my_project ~/Projects/my_project
    ```
* **Jump to a bookmark**:
    ```bash
    lim tp my_project
    # Then in your current terminal:
    ./l.<TAB><ENTER> # (press Tab to auto-complete)
    ```

### Configuration

* **Docker Cache**: LIMbo caches Docker container information in `~/.config/lim/docker_cache.json`.
* **Bookmarks**: Your saved bookmarks are stored in `~/.config/lim/bookmarks.json`.
* **Cache Expiration**: The Docker cache automatically refreshes every 5 minutes by default, but this can be configured in `~/.config/lim/config.json`.

---
# LIMbo: Ваш интуитивный навигатор Linux и Docker
# Возможно, местами недоработан. Находится в долгосрочной разработке. Используйте на свой страх и риск.
Этот проект распространяется под лицензией Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).
Подробности смотрите в файле [LICENSE](LICENSE).

[English](#english) | [Русский](#русский)

Устали от `htop` и его ограниченных форков? Встречайте LIMbo – мощный, интуитивно понятный и высокофункциональный текстовый пользовательский интерфейс (TUI) для мониторинга вашей Linux-системы и навигации по вашим Docker-окружениям. Разработанный для скорости и простоты использования, LIMbo выходит за рамки базового мониторинга, предлагая глубокие аналитические данные и бесшовные переходы между директориями с минимальным количеством нажатий клавиш.

<a name="русский"></a>

### Почему LIMbo?

Традиционным TUI-мониторам, такие как `htop`, часто не хватает функциональности, особенно при управлении сложными Docker-средами или частых переходах между директориями проектов. LIMbo появился из потребности в более комплексном и эргономичном инструменте. Моя философия дизайна ставит во главу угла эффективность: даже навигационные скрипты (`l.sh`, `b.sh`) названы так, чтобы их можно было вводить одной рукой и быстро дополнять с помощью Tab для плавного рабочего процесса.

### Возможности

#### **Системный Монитор (Команда `lim` по умолчанию)**

Основная команда `lim` запускает мощный, интерактивный TUI-монитор системы, предлагая информацию о производительности вашей системы и процессах в реальном времени.

* **Полный Обзор**: Отображает информацию о ЦПУ, памяти, ГПУ, вводе/выводе дисков, сетевом вводе/выводе, средних нагрузках, времени безотказной работы и общую системную информацию.
* **Динамический Список Процессов**:
    * **Подробная Информация о Процессах**: Просмотр PID, имени пользователя, использования ЦПУ, использования памяти (RSS и VMS) и "умного" отображаемого имени для процессов.
    * **"Умные" Имена Процессов**: Автоматически преобразует общие имена исполняемых файлов (например, `python3`, `node`, `mysqld`) в более описательные метки (например, "Python Script", "Node.js", "MySQL"). Для процессов Java пытается извлечь имя JAR-файла.
    * **Индикатор Изменения Памяти**: Легко отслеживайте процессы с увеличивающимся (`+`), уменьшающимся (`-`) или неизменным (`*`) размером Resident Set Size (RSS) с момента последнего обновления.
    * **Подсветка Ресурсов**: Процессы, потребляющие значительное количество ЦПУ или памяти, подсвечиваются для быстрой идентификации.
    * **Интерактивная Сортировка**: Сортируйте список процессов по различным метрикам (RSS, CPU, MEM%, PID, VMS, Name) нажатием `Tab` (вперед) или `Shift+Tab` (назад). Также конкретные клавиши (`r`, `c`, `m`, `p`, `v`, `n`) напрямую сортируют по RSS, ЦПУ, памяти, PID, VMS и имени соответственно.
    * **Поиск/Фильтр**: (Планируется на будущее, еще не реализовано)
* **Интерактивные Режимы**: Переключайтесь между специализированными режимами для целевых действий:
    * **Режим Docker (`d`)**: Фильтрует список процессов, показывая только процессы Docker-контейнеров.
        * **Идентификация Контейнера**: Четко показывает связанное имя или короткий ID Docker-контейнера.
        * **Действия Docker (Enter)**: При выборе процесса Docker нажатие `Enter` открывает меню для:
            * **Просмотра (`i`)**: Запускает `docker inspect` и отображает подробную информацию о контейнере во всплывающем окне.
            * **Перезапуска (`r`)**: Немедленно перезапускает выбранный Docker-контейнер.
            * **Shell (`s`)**: Предоставляет команду `docker exec -it <container_id> /bin/bash` для удобного копирования, чтобы открыть оболочку внутри контейнера.
    * **Режим Убийцы (`k`)**: Включает меню подтверждения "убийства" для выбранных процессов.
        * **Подтверждение Сигнала (Enter)**: При выборе процесса нажатие `Enter` вызывает запрос на отправку `SIGTERM` (`s`) или `SIGKILL (-9)` (`k`).
* **Навигация**: Используйте `↑`/`↓` для построчной навигации, `PgUp`/`PgDn` для прокрутки страниц и `Home`/`End` для перехода в начало/конец списка. Поддерживается выбор мышью.
* **Помощь (`h`)**: Доступ к встроенному экрану помощи с описанием сочетаний клавиш и функций.
* **Обновление (`r`)**: Принудительное обновление кеша Docker.

#### **Навигатор Docker и Закладок (`lim list` или `lim nav`)**

Этот специализированный TUI позволяет быстро переходить к директориям проектов Docker Compose или к пользовательским закладкам.

* **Объединенный Список**: Отображает как Docker-контейнеры (с их путем compose и статусом), так и пользовательские закладки директорий в одном, сортируемом списке.
* **Быстрая Навигация (`g` или `Enter`)**: Выберите элемент и нажмите `g` или `Enter`, чтобы сгенерировать одноразовые навигационные скрипты (`l.sh` и `b.sh`) в вашей *текущей* директории.
    * **`l.sh`**: Маленький, самоудаляющийся скрипт, который переводит вас в целевую директорию и запускает новую `bash` оболочку. Он информирует вас о том, как вернуться в исходную директорию.
    * **`b.sh`**: Созданный *внутри целевой директории*, этот скрипт возвращает вас в *исходную* рабочую директорию. Оба скрипта самоудаляются через несколько секунд для чистоты. Это означает, что вы можете ввести `./l.sh` (с автодополнением по Tab) из любого места, чтобы мгновенно перейти к вашему проекту, и `./b.sh`, чтобы вернуться, с тем же удобством одной руки и быстрым завершением.
* **Docker Inspect (`i`)**: Аналогично основному монитору, нажатие `i` на записи Docker запускает `docker inspect` для получения подробной информации.
* **Управление Закладками**:
    * **Добавить Закладку (`a`)**: Интерактивно добавляйте новую закладку с именем и целевым путем (по умолчанию – текущая директория).
    * **Удалить Закладку (`d`)**: Удаляет выбранную закладку.

#### **CLI Команды**

Помимо TUI, LIMbo предоставляет набор мощных утилит командной строки для быстрых задач, с автодополнением Bash для общих аргументов.

* `lim inspect <container_id_или_имя>` (`lim i`): Отображает вывод `docker inspect` для данного контейнера с форматированием Rich, если оно доступно.
* `lim go <container_id_или_имя>`: Генерирует скрипты `l.sh` и `b.sh` для перехода в директорию Docker Compose указанного контейнера.
* `lim updatecache`: Принудительно обновляет кеш Docker-контейнеров, используемый как TUI, так и CLI-командами. Этот кеш обычно обновляется каждые 5 минут с помощью cron-задачи.
* `lim tp <имя_закладки>`: Переходит в закладку, аналогично `lim go`, но для пользовательских путей.
    * `lim tp add <имя> [путь]`: Добавляет новую закладку. Путь по умолчанию – текущая директория.
    * `lim tp del <имя>`: Удаляет закладку.
    * `lim tp list`: Выводит все сохраненные закладки в красиво отформатированной таблице.

### Почему `l.sh` и `b.sh`?

Идея `l.sh` (от **L**aunch — запуск) и `b.sh` (от **B**ack — назад) — это чистая эргономика. Это намеренно короткие, односимвольные имена, чтобы минимизировать ввод. В сочетании с автодополнением Bash по Tab (`./l.sh<TAB>`) они обеспечивают беспрецедентную скорость для навигации по глубоко вложенным директориям проектов или папкам Docker Compose, значительно превосходя традиционные команды `cd` или сложные алиасы.

Когда вы используете `lim tui` или `lim go`, эти скрипты *временно* создаются в вашей *текущей* директории. Это означает, что вам не нужно беспокоиться об их управлении; они появляются, когда нужны, и самоудаляются вскоре после использования. Скрипт `l.sh` немедленно переводит вас в целевую директорию и запускает новую оболочку, обеспечивая плавный переход. Скрипт `b.sh`, созданный в целевой директории, позволяет вернуться туда, откуда вы начали, с тем же удобством одной руки и быстрым завершением.

### Установка

1.  **Клонируйте репозиторий**:
    ```bash
    git clone https://github.com/srose69/Lim
    cd lim
    ```

2.  **Запустите установщик**:
    ```bash
    chmod +x install.sh
    sudo ./install.sh
    ```
    Установщик выполнит:
    * Обновление списков пакетов и установка основных зависимостей (`python3`, `pip`, `jq`, `python3-venv`).
    * Установка библиотек Python (`psutil`, `rich`, `docker`).
    * Проверку и установку Docker, если он отсутствует, а также добавление вашего пользователя в группу `docker` (требует выхода из системы/входа или запуска `newgrp docker` для вступления изменений в силу).
    * Копирование скриптов LIMbo в `/usr/lib/lim` и создание символических ссылок (`lim`, `lim_update_cache.py`) в `/usr/local/bin` и `/usr/local/sbin`.
    * Настройку cron-задачи для автоматического обновления кеша Docker каждые 5 минут.
    * Установку автодополнения Bash для команд `lim` в `/etc/bash_completion.d/`.

    *Примечание: Если вы были добавлены в группу `docker` во время установки, вам потребуется выйти из системы и войти снова, или выполнить `newgrp docker`, чтобы изменения вступили в силу.*

### Использование

* **Запустить основной монитор**:
    ```bash
    lim
    ```
* **Запустить навигатор Docker и закладок**:
    ```bash
    lim tui
    ```
* **Перейти в директорию Docker Compose**:
    ```bash
    lim go <имя_или_id_контейнера>
    # Затем в вашем текущем терминале:
    ./l.sh # (и нажмите Tab для автозавершения)
    ```
* **Добавить закладку**:
    ```bash
    lim tp add my_project ~/Projects/my_project
    ```
* **Перейти по закладке**:
    ```bash
    lim tp my_project
    # Затем в вашем текущем терминале:
    ./l.<TAB><ENTER> # ( Tab для автозавершения)
    ```

### Конфигурация

* **Кеш Docker**: LIMbo кэширует информацию о Docker-контейнерах в `~/.config/lim/docker_cache.json`
* **Закладки**: Ваши сохраненные закладки хранятся в `~/.config/lim/bookmarks.json`
* **Срок действия кеша**: Кеш Docker автоматически обновляется каждые 5 минут по умолчанию, но это можно настроить в `~/.config/lim/config.json`
