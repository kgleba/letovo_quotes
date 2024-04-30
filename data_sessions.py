from __future__ import annotations

from functools import wraps

from config import DATA_FILES

__all__ = ['SessionManager', 'sessioned_data']


class Session:
    def __init__(self, parent: SessionManager, source: str):
        self.parent = parent
        self.source = source

    def end(self):
        self.parent.end_current_session(self.source)


class SessionManager:
    def __init__(self):
        self.queue: dict[str, list[Session]] = {source: [] for source in DATA_FILES}

    def init_session(self, source: str) -> Session:
        assert self.queue.get(source) is not None, 'Unknown source provided'

        new_session = Session(self, source)
        self.queue[source].append(new_session)

        while self.queue[source][0] != new_session:
            pass

        return new_session

    def end_current_session(self, source: str):
        self.queue[source].pop(0)


def sessioned_data(manager: SessionManager, source: str):
    def decorator(func):
        func.__dict__['sessioned_sources'] = func.__dict__.get('sessioned_sources', []) + [source]

        @wraps(func)
        def wrapper(*args, **kwargs):
            parent = locals()['func']

            sessioned_sources = parent.__dict__.get('sessioned_sources')
            if sessioned_sources is not None and source in sessioned_sources:
                return func(*args, **kwargs)

            session = manager.init_session(source)
            result = func(*args, **kwargs)
            session.end()

            return result

        return wrapper

    return decorator
