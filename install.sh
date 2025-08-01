#!/bin/bash

set -e

# --- Настройки ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
INSTALL_DIR="/usr/lib/lim"
SOURCE_SCRIPT="lim"
DEST_BIN="/usr/local/bin/lim"
CACHE_UPDATER_SCRIPT="lim_update_cache.py"
DEST_CACHE_UPDATER="/usr/local/sbin/$CACHE_UPDATER_SCRIPT"
COMPLETION_SCRIPT="lim-completion.bash"
DEST_COMPLETION_DIR="/etc/bash_completion.d"
CRON_FILE="/etc/cron.d/lim_cache_updater"
CRON_SCHEDULE="*/5 * * * *"

# --- Функции ---
install_dependencies() {
    echo "--- Updating package list ---"
    sudo apt-get update -y > /dev/null

    echo "--- Installing base dependencies (python, pip, jq, docker) ---"
    sudo apt-get install -y python3 python3-pip python3-venv jq &> /dev/null
    
    echo "--- Installing required python libraries (psutil, rich, docker) ---"
    pip install psutil rich docker &> /dev/null
}

install_docker() {
    echo "--- Checking and installing Docker ---"
    if ! command -v docker &> /dev/null
    then
        echo "Docker not found. Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh

        echo "--- Adding current user to docker group ---"
        sudo groupadd -f docker
        sudo usermod -aG docker "$USER"
        echo "!!! Important: Group changes require logout/login or run: newgrp docker"
    else
        echo "Docker is already installed."
        if ! groups "$USER" | grep -q '\bdocker\b'; then
            echo "Adding current user $USER to docker group..."
            sudo usermod -aG docker "$USER"
            echo "!!! Important: Group changes require logout/login or run: newgrp docker"
        fi
    fi

    echo "--- Checking Docker Daemon availability ---"
    if ! docker info > /dev/null 2>&1; then
        echo "Cannot connect to Docker daemon. Ensure it is running."
        echo "Try: sudo systemctl start docker"
        echo "And: sudo systemctl enable docker"
    fi
}

install_files() {
    echo "--- Creating installation directory: $INSTALL_DIR ---"
    sudo mkdir -p "$INSTALL_DIR"

    echo "--- Copying all Python scripts (*.py) to $INSTALL_DIR ---"
    sudo cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
    
    echo "--- Copying main executable script to $INSTALL_DIR ---"
    sudo cp "$SCRIPT_DIR/$SOURCE_SCRIPT" "$INSTALL_DIR/"

    echo "--- Creating symlinks ---"
    sudo ln -sf "$INSTALL_DIR/$SOURCE_SCRIPT" "$DEST_BIN"
    sudo chmod +x "$DEST_BIN"
    
    sudo ln -sf "$INSTALL_DIR/$CACHE_UPDATER_SCRIPT" "$DEST_CACHE_UPDATER"
    sudo chmod +x "$DEST_CACHE_UPDATER"

    echo "Scripts installed and symlinks created."
}

install_cache_updater() {
    if [ -f "$SCRIPT_DIR/$CACHE_UPDATER_SCRIPT" ]; then
        # Создаем директорию для логов, если ее нет
        sudo mkdir -p "$LOG_DIR"

        CRON_JOB="$CRON_SCHEDULE root    /usr/bin/python3 $DEST_CACHE_UPDATER >> $LOG_DIR/$LOG_FILE 2>&1"

        echo "--- Настройка cron задачи для обновления кэша каждые 5 минут ---"
        echo "$CRON_JOB" | sudo tee "$CRON_FILE" > /dev/null
        sudo chmod 644 "$CRON_FILE"
        sudo systemctl restart cron

        echo "Cron задача добавлена в $CRON_FILE"
        echo "Логи обновления кэша будут в $LOG_DIR/$LOG_FILE"
    else
        echo "--- Cache update script '$CACHE_UPDATER_SCRIPT' not found, cron job not configured ---"
    fi
}

install_completion() {
    if [ -f "$SCRIPT_DIR/$COMPLETION_SCRIPT" ]; then
        echo "--- Installing bash completion ---"
        if [ -d "$DEST_COMPLETION_DIR" ]; then
            sudo cp "$INSTALL_DIR/$COMPLETION_SCRIPT" "$DEST_COMPLETION_DIR/lim"
            echo "Completion installed to $DEST_COMPLETION_DIR/lim"
            echo "Completion will be available in a new bash session."
        else
            echo "!!! Directory $DEST_COMPLETION_DIR not found. Completion not installed."
            echo "Maybe install bash-completion: sudo apt-get install bash-completion"
        fi
    else
        echo "--- Completion script '$COMPLETION_SCRIPT' not found, skipping ---"
    fi
}

# --- Основная логика ---

install_dependencies
install_docker
install_files
install_cache_updater
install_completion

echo ""
echo "--- Installation finished! ---"
echo "You can run the monitor with: lim"
echo "If you were just added to the 'docker' group, remember to logout/login or run 'newgrp docker'."

exit 0