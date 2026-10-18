"""Recover unmarked UTF-8 ZIP labels without changing archive member lookup keys."""


def readable_zip_name(name: str, *, utf8: bool = False) -> str:
    """Recover a CP437-decoded ZIP name, respecting an explicit UTF-8 language flag."""
    if utf8:
        return name
    try:
        return name.encode("cp437").decode("utf-8")
    except UnicodeError:
        # Genuine legacy CP437 and already-correct Unicode names remain untouched.
        return name


def import_file_name(db, row) -> str:
    """Recover historical ZIP labels; a successful parser receipt protects normalized names."""
    if not row.parent_id:
        return row.name
    recovered = readable_zip_name(row.name)
    if recovered == row.name:
        return row.name
    from .import_models import ImportFile
    from .job_models import Job

    parent = db.get(ImportFile, row.parent_id)
    job = db.get(Job, parent.job_id) if parent and parent.job_id else None
    if job and job.result and job.result.get("filename_encoding") == "unicode":
        return row.name
    return recovered
