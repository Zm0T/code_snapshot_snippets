import os
import difflib
from datetime import datetime
from typing import Dict, List, Set, Optional


def find_project_root(required_paths: Optional[List[str]] = None) -> str:
    """
    Универсальный поиск корня проекта, двигаясь от директории текущего файла вверх.

    Аргументы:
    ---------
    required_paths : List[str], optional
        Список директорий и/или файлов, которые должны находиться в корне проекта.
        Проверка идёт на их существование в текущей директории (относительно которой идёт поиск).

    Возвращает:
    -----------
    str
        Путь к обнаруженному корню проекта. Если ничего не найдено,
        возвращается директория, в которой расположен текущий скрипт.
    """
    if required_paths is None:
        # Если не указали обязательные пути, по умолчанию
        # просто используем папку со скриптом.
        return os.path.dirname(os.path.abspath(__file__))

    current_dir = os.path.dirname(os.path.abspath(__file__))

    while True:
        # Проверяем, все ли указанные пути существуют в текущей директории
        if all(os.path.exists(os.path.join(current_dir, path)) for path in required_paths):
            return current_dir

        # Поднимаемся на уровень выше
        parent_dir = os.path.dirname(current_dir)

        # Если уже выше некуда подниматься — выходим
        if parent_dir == current_dir:
            # Ничего не нашли, возвращаем директорию скрипта
            return os.path.dirname(os.path.abspath(__file__))

        current_dir = parent_dir


def get_project_structure(
        start_path: str,
        indent: str = '  ',
        excluded_directories: Optional[List[str]] = None,
        excluded_extensions: Optional[Set[str]] = None
) -> str:
    """
    Генерирует строковое представление структуры проекта.

    Параметры:
    ----------
    start_path : str
        Путь, с которого начинается обход (обычно корень проекта или одна из директорий).
    indent : str
        Отступ для вложенных директорий/файлов.
    excluded_directories : List[str], optional
        Список директорий, которые не нужно включать в структуру.
    excluded_extensions : Set[str], optional
        Список расширений файлов, которые не нужно включать.
    """
    if excluded_directories is None:
        excluded_directories = []
    if excluded_extensions is None:
        excluded_extensions = set()

    structure = []

    for root, dirs, files in os.walk(start_path):
        # Исключаем нежелательные директории
        dirs[:] = [d for d in dirs if d not in excluded_directories]

        level = root.replace(start_path, '').count(os.sep)
        indent_str = indent * level

        folder = os.path.basename(root)
        if level == 0:
            structure.append(f"{folder}/")
        else:
            structure.append(f"{indent_str}{folder}/")

        subindent = indent * (level + 1)
        for f in sorted(files):
            # Пропускаем файлы с нежелательными расширениями
            if any(f.endswith(ext) for ext in excluded_extensions):
                continue
            structure.append(f"{subindent}{f}")

    return '\n'.join(structure)


class ProjectSnapshot:
    def __init__(self, snapshot_file: str = "project_snapshot.txt", required_paths: Optional[List[str]] = None):
        """
        Инициализация снимка проекта.

        Параметры:
        ----------
        snapshot_file : str
            Имя (или путь) файла, в который будет сохранён снимок.
        required_paths : List[str], optional
            Список директорий и/или файлов, на основе которых определяется "корень" проекта.
            Если None, берётся директория, в которой лежит скрипт.
        """
        # Находим корень проекта (или директорию со скриптом, если required_paths не указаны)
        self.project_root = find_project_root(required_paths=required_paths)

        # Сохраняем файл снимка в той же директории, где находится скрипт
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.snapshot_file = os.path.join(script_dir, snapshot_file)

        self.previous_snapshots: Dict[str, str] = {}

        print(f"\n📁 Корень проекта: {self.project_root}")
        print(f"📄 Файл снимка будет создан в: {self.snapshot_file}")

        self.load_previous_snapshots()

    def load_previous_snapshots(self) -> None:
        """
        Считывает предыдущий снимок из файла (если он существует) и
        заполняет словарь self.previous_snapshots содержимым каждого файла.
        """
        if not os.path.exists(self.snapshot_file):
            print("ℹ️  Первый запуск - будет создан новый файл снимка")
            return

        try:
            with open(self.snapshot_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Отделяем структуру проекта (если есть) от остального содержимого
                if "Project Structure:" in content:
                    content = content.split("End Project Structure", 1)[1]

                # Разбиваем на секции по разделителю '====...'
                sections = content.split('=' * 50 + '\n')

                current_file = None
                current_content = []
                in_final_content = False

                for section in sections:
                    if not section.strip():
                        continue

                    lines = section.strip().split('\n')
                    for line in lines:
                        if line.startswith('File: '):
                            # Если мы уже обрабатывали какой-то файл, сохраняем его
                            if current_file and current_content:
                                self.previous_snapshots[current_file] = '\n'.join(current_content)

                            # Начинаем новую секцию файла
                            current_file = line.replace('File: ', '').strip()
                            current_content = []
                            in_final_content = False

                        elif line.strip() == "FINAL CONTENT:":
                            # С этого момента идёт финальное содержимое файла
                            in_final_content = True
                            current_content = []

                        elif line.strip() and not line.startswith('Snapshot created at:'):
                            # Добавляем строки в контент, только если находимся в блоке FINAL CONTENT
                            if in_final_content and not any(line.startswith(x) for x in ['NEW', 'DELETED']):
                                current_content.append(line)

                # После цикла нужно сохранить последний файл
                if current_file and current_content:
                    self.previous_snapshots[current_file] = '\n'.join(current_content)

        except Exception as e:
            print(f"⚠️  Ошибка при загрузке предыдущего снимка: {e}")
            self.previous_snapshots = {}

    def create_snapshot(
            self,
            included_directories: List[str],
            included_extensions: Set[str],
            excluded_directories: Optional[List[str]] = None,
            excluded_extensions: Optional[Set[str]] = None
    ) -> bool:
        """
        Создает снимок проекта, анализируя только файлы в директориях `included_directories`
        с расширениями `included_extensions`. При этом исключаются директории из `excluded_directories`
        и файлы с расширениями из `excluded_extensions`.

        Возвращает:
        -----------
        bool : были ли обнаружены изменения (True/False).
        """
        if excluded_directories is None:
            excluded_directories = []
        if excluded_extensions is None:
            excluded_extensions = set()

        current_snapshots = {}
        changes_detected = False
        new_files = []
        modified_files = []
        deleted_files = []

        print("\n🔍 Сканирование проекта...")

        # Сбор текущего состояния файлов
        for directory in included_directories:
            directory_path = os.path.join(self.project_root, directory)
            if not os.path.exists(directory_path):
                continue

            for root, dirs, files in os.walk(directory_path):
                # Исключаем нежелательные директории
                dirs[:] = [d for d in dirs if d not in excluded_directories]

                for file in files:
                    # Проверяем, подходит ли файл под включаемые и не исключён ли он
                    if any(file.endswith(ext) for ext in included_extensions):
                        if any(file.endswith(ext) for ext in excluded_extensions):
                            continue  # Если расширение из запрещённых, пропускаем

                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                rel_path = os.path.relpath(file_path, self.project_root)
                                current_snapshots[rel_path] = content
                        except Exception as e:
                            print(f"⚠️  Ошибка при чтении файла {file_path}: {e}")

        # Определяем изменения
        for file_path, current_content in current_snapshots.items():
            # Проверяем, есть ли файл в предыдущем снимке
            if file_path not in self.previous_snapshots:
                new_files.append(file_path)
                changes_detected = True
            else:
                prev_content = self.previous_snapshots[file_path]
                if prev_content != current_content:
                    modified_files.append(file_path)
                    changes_detected = True

        # Проверяем удалённые файлы
        for old_file in self.previous_snapshots:
            if old_file not in current_snapshots:
                deleted_files.append(old_file)
                changes_detected = True

        # Выводим информацию об изменениях
        if new_files:
            print("\n✨ Новые файлы:")
            for file in new_files:
                print(f"   + {file}")

        if modified_files:
            print("\n📝 Изменённые файлы:")
            for file in modified_files:
                print(f"   ~ {file}")

        if deleted_files:
            print("\n🗑️  Удалённые файлы:")
            for file in deleted_files:
                print(f"   - {file}")

        if not changes_detected:
            print("\n✅ Изменений не обнаружено")
            return False

        # Запись снимка
        try:
            with open(self.snapshot_file, 'w', encoding='utf-8') as f:
                # Записываем структуру проекта
                f.write("Project Structure:\n")
                f.write("=" * 50 + "\n")
                for directory in included_directories:
                    directory_path = os.path.join(self.project_root, directory)
                    if os.path.exists(directory_path):
                        f.write(
                            get_project_structure(
                                directory_path,
                                excluded_directories=excluded_directories,
                                excluded_extensions=excluded_extensions
                            ) + "\n"
                        )
                f.write("=" * 50 + "\n")
                f.write("End Project Structure\n\n")

                # Записываем временную метку
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"Snapshot created at: {timestamp}\n\n")

                # Записываем файлы
                for file_path, current_content in sorted(current_snapshots.items()):
                    f.write('=' * 50 + '\n')
                    f.write(f"File: {file_path}\n")
                    f.write('=' * 50 + '\n')

                    if file_path in new_files:
                        # Новый файл
                        f.write("NEW\n")
                        f.write(current_content + '\n')
                        f.write("\nFINAL CONTENT:\n")
                        f.write(current_content + '\n')
                    else:
                        prev_content = self.previous_snapshots.get(file_path, '')
                        if prev_content != current_content:
                            # Изменённый файл
                            diff = list(difflib.unified_diff(
                                prev_content.splitlines(),
                                current_content.splitlines(),
                                fromfile=file_path,
                                tofile=file_path,
                                lineterm=''
                            ))
                            f.write('\n'.join(diff) + '\n')
                            f.write("\nFINAL CONTENT:\n")
                            f.write(current_content + '\n')
                        else:
                            # Файл без изменений (добавляем FINAL CONTENT для полноты)
                            f.write("\nFINAL CONTENT:\n")
                            f.write(current_content + '\n')

                # Записываем удалённые файлы
                for file_path in deleted_files:
                    f.write('=' * 50 + '\n')
                    f.write(f"File: {file_path}\n")
                    f.write('=' * 50 + '\n')
                    f.write("DELETED\n")

            print(f"\n💾 Снимок сохранён в: {self.snapshot_file}")
            print(f"⏰ Время создания: {timestamp}")
            return True

        except Exception as e:
            print(f"❌ Ошибка при создании снимка: {e}")
            return False


def main():
    print("\n🚀 Запуск сканирования кода...")

    # Выводим текущую директорию
    print(f"Текущая директория: {os.getcwd()}")

    snapshot = ProjectSnapshot(
        snapshot_file="project_snapshot.txt",
        required_paths=['.']
    )

    # Используем абсолютный путь до проекта
    project_path = os.path.join(os.getcwd())
    print(f"Сканируем проект по пути: {project_path}")

    included_directories = [
        'src',           # Исходный код React Native
        'app',           # Для новой файловой системы Expo
        'assets',        # Медиа-файлы, изображения и т.д.
        'components',    # React компоненты
        'screens',       # Экраны приложения
        'navigation',    # Навигация
        'hooks',         # Кастомные хуки
        'utils',         # Утилиты
        'services',      # Сервисы (API и т.д.)
        'store'         # Состояние приложения (Redux/Context)
    ]

    included_extensions = {
        '.js', '.jsx',   # JavaScript файлы
        '.ts', '.tsx',   # TypeScript файлы
        '.json',         # Конфигурационные файлы
        '.native.js',    # Специфичные для React Native файлы
        '.style.js',     # Файлы стилей
        '.config.js'     # Конфигурационные файлы
    }

    excluded_directories = [
        'node_modules',
        '.expo',
        '.expo-shared',
        'build',
        'dist',
        '.git',
        'android',      # Сгенерированные нативные файлы
        'ios',          # Сгенерированные нативные файлы
        'web-build',    # Веб-сборка Expo
        'coverage'      # Файлы покрытия тестов
    ]

    excluded_extensions = {
        '.log',
        '.lock',
        '.expo',
        '.gradle',
        '.pbxproj',
        '.xcworkspace',
        '.idea',
        '.vscode',
        '.DS_Store'
    }

    snapshot.create_snapshot(
        included_directories=included_directories,
        included_extensions=included_extensions,
        excluded_directories=excluded_directories,
        excluded_extensions=excluded_extensions
    )


if __name__ == "__main__":
    main()
