import docker  # Для взаимодействия с Docker API
import json  # Для работы с JSON-данными
import os  # Для операций с файловой системой
import time  # Для работы со временем
import datetime  # Для работы с датой и временем
import sys  # Для доступа к stderr
from pathlib import Path  # Для удобной работы с путями
from typing import Dict, List, Optional, Any  # Для аннотаций типов

#  Путь к файлу кэша Docker (пользователь может изменить)
CACHE_FILE = Path.home() / ".config/lim/docker_cache.json"

# Время жизни кэша (в секундах) - по умолчанию 5 минут
CACHE_EXPIRATION = 300  # 5 минут в секундах


def load_config() -> Dict[str, Any]:
    """
    Загружает пользовательские настройки из JSON-файла.

    Файл настроек находится по пути ~/.config/lim/config.json.
    Если файл не найден или содержит ошибки, используются значения по умолчанию.
    """

    config_path = Path.home() / ".config/lim/config.json"
    config: Dict[str, Any] = {}  # Инициализируем пустой словарь для настроек

    if config_path.is_file():  # Проверяем, существует ли файл
        try:
            with open(config_path, "r") as f:
                config = json.load(f)  # Загружаем JSON из файла
        except json.JSONDecodeError:
            print(
                f"Предупреждение: Некорректный JSON в файле настроек: {config_path}",
                file=sys.stderr,
            )
        except FileNotFoundError:
            print(
                f"Предупреждение: Файл настроек не найден: {config_path}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Ошибка при загрузке настроек: {e}", file=sys.stderr)
    else:
        print(
            f"Файл настроек не найден: {config_path}. Используются значения по умолчанию.",
            file=sys.stderr,
        )

    config.setdefault(
        "cache_expiration", CACHE_EXPIRATION
    )  # Устанавливаем значение по умолчанию для времени жизни кэша
    return config


def load_docker_cache() -> Dict[str, Any]:
    """
    Загружает кэш Docker из файла.

    Если файл кэша не существует или содержит ошибки, возвращает пустой кэш.
    """

    cache: Dict[str, Any] = {
        "containers": {},
        "timestamp": 0,
    }  # Инициализируем структуру кэша
    if CACHE_FILE.is_file():  # Проверяем, существует ли файл кэша
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)  # Загружаем JSON из файла кэша
        except (FileNotFoundError, json.JSONDecodeError):
            print(
                f"Предупреждение: Не удалось загрузить файл кэша: {CACHE_FILE}",
                file=sys.stderr,
            )
    return cache


def save_docker_cache(cache_data: Dict[str, Any]) -> None:
    """Saves the Docker cache to a file."""

    cache_dir = Path.home() / ".config/lim"  # Определяем путь к директории кэша
    cache_dir.mkdir(
        parents=True, exist_ok=True
    )  # Создаем директорию, если она не существует

    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=4)
    except IOError:
        print(f"Error saving cache to {CACHE_FILE}", file=sys.stderr)


def find_compose_path(container: docker.models.containers.Container) -> Optional[str]:
    """
    Находит директорию docker-compose.yml для контейнера.

    Ищет путь в метках контейнера.
    """

    labels = container.labels
    compose_workdir = labels.get(
        "com.docker.compose.project.working_dir"
    )  # Пытаемся получить путь из метки com.docker.compose.project.working_dir
    if compose_workdir:
        return compose_workdir

    compose_config = labels.get(
        "com.docker.compose.project.config_files"
    )  # Пытаемся получить путь из метки com.docker.compose.project.config_files
    if compose_config:
        try:
            first_config_path = Path(
                compose_config.split(",")[0]
            )  # Берем первый путь из списка путей
            if (
                first_config_path.is_absolute() and first_config_path.is_file()
            ):  # Если путь абсолютный и указывает на файл
                return str(
                    first_config_path.parent
                )  # Возвращаем родительскую директорию
            else:
                return str(first_config_path)  # Иначе возвращаем сам путь
        except Exception:
            pass  # Игнорируем ошибки при обработке пути
    return None


def update_docker_cache(config: Dict[str, Any]) -> None:
    """
    Обновляет кэш Docker.

    Получает информацию о запущенных контейнерах и сохраняет ее в файл кэша.
    """

    cache_data: Dict[str, Any] = {
        "containers": {},
        "timestamp": time.time(),
        "error": None,
    }  # Инициализируем структуру данных для кэша

    try:
        client = docker.from_env()  # Подключаемся к Docker Daemon
        containers = client.containers.list(
            all=True
        )  # Получаем список всех контейнеров (запущенных и остановленных)

        for container in containers:
            try:
                container.reload()  # Обновляем информацию о контейнере (на случай изменений)
                container_id = container.short_id  # Получаем короткий ID контейнера
                compose_path = find_compose_path(
                    container
                )  # Находим путь к docker-compose.yml
                image_tag = (
                    container.image.tags[0]
                    if container.image and container.image.tags
                    else "unknown"
                )  # Получаем тег образа, если есть

                container_info: Dict[str, Any] = {
                    "id": container.id,
                    "short_id": container.short_id,
                    "name": container.name,
                    "image": image_tag,
                    "status": container.status,
                    "compose_path": compose_path,
                }  # Собираем информацию о контейнере
                cache_data["containers"][
                    container_id
                ] = container_info  # Добавляем информацию в кэш

            except docker.errors.NotFound as e:
                print(
                    f"Предупреждение: Контейнер не найден во время обновления кэша: {e}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Ошибка при обработке контейнера {container.name}: {e}",
                    file=sys.stderr,
                )

    except docker.errors.DockerException:
        cache_data["error"] = "Docker daemon не доступен"
        print("Ошибка: Docker daemon не доступен.", file=sys.stderr)

    save_docker_cache(cache_data)  # Сохраняем обновленные данные в файл кэша


def is_cache_valid(config: Dict[str, Any], cache_data: Dict[str, Any]) -> bool:
    """
    Проверяет, является ли кэш Docker актуальным.

    Сравнивает время последнего обновления кэша с заданным временем жизни.
    """

    if (
        "timestamp" not in cache_data
    ):  # Если в кэше нет информации о времени обновления, считаем его невалидным
        return False
    expiration = config.get(
        "cache_expiration", CACHE_EXPIRATION
    )  # Получаем время жизни кэша из настроек
    return (
        time.time() - cache_data["timestamp"] < expiration
    )  # Проверяем, не истекло ли время жизни


def main() -> None:
    """
    Основная функция скрипта.

    Загружает настройки, проверяет актуальность кэша и при необходимости обновляет его.
    """

    config = load_config()  # Загружаем настройки пользователя
    cache_data = load_docker_cache()  # Загружаем данные из кэша

    if not is_cache_valid(config, cache_data):  # Проверяем актуальность кэша
        update_docker_cache(config)  # Обновляем кэш, если он не актуален
        cache_data = (
            load_docker_cache()
        )  # Перезагружаем данные из кэша после обновления

    if cache_data.get(
        "error"
    ):  # Выводим предупреждение, если при обновлении кэша произошла ошибка Docker
        print(
            f"Предупреждение: Используется потенциально устаревший кэш. Ошибка Docker: {cache_data['error']}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
