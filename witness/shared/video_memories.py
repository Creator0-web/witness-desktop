"""Video memory archive. Drop or browse a video into any calendar day,
browse back month to month later. Just files on disk under
video_memories/YYYY-MM-DD/ -- no database needed, easy to back up or
inspect by hand.
"""
import os
import shutil

BASE_DIR = "video_memories"
VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")


def _day_dir(day: str) -> str:
    path = os.path.join(BASE_DIR, day)
    os.makedirs(path, exist_ok=True)
    return path


def videos_for_day(day: str) -> list:
    """Filenames only (not full paths), sorted."""
    path = os.path.join(BASE_DIR, day)
    if not os.path.isdir(path):
        return []
    return sorted(f for f in os.listdir(path)
                  if f.lower().endswith(VIDEO_EXTS))


def video_path(day: str, filename: str) -> str:
    return os.path.join(BASE_DIR, day, filename)


def add_video(day: str, source_path: str) -> str:
    """Copies source_path into that day's folder. Returns the new full
    path. Raises FileNotFoundError if source_path doesn't exist, and
    ValueError if it doesn't look like a video file."""
    if not os.path.isfile(source_path):
        raise FileNotFoundError(source_path)
    if not source_path.lower().endswith(VIDEO_EXTS):
        raise ValueError(f"Not a recognized video file: {source_path}")

    day_dir = _day_dir(day)
    filename = os.path.basename(source_path)
    dest = os.path.join(day_dir, filename)

    # avoid silently overwriting a same-named file from a different upload
    base, ext = os.path.splitext(filename)
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(day_dir, f"{base}_{n}{ext}")
        n += 1

    shutil.copy2(source_path, dest)
    return dest


def days_with_videos_in_month(year: int, month: int) -> set:
    """Set of day-numbers (ints) in that month that have at least one
    video -- used to draw a dot on the calendar grid without having to
    re-scan every folder on every render."""
    if not os.path.isdir(BASE_DIR):
        return set()
    prefix = f"{year:04d}-{month:02d}-"
    result = set()
    for name in os.listdir(BASE_DIR):
        if name.startswith(prefix) and len(name) == 10:
            full_path = os.path.join(BASE_DIR, name)
            if os.path.isdir(full_path) and videos_for_day(name):
                try:
                    result.add(int(name[8:10]))
                except ValueError:
                    pass
    return result


def open_video(path: str):
    """Open with the OS default video player. Windows-only, same
    assumption the rest of this app already makes."""
    os.startfile(path)
