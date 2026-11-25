"""Layered stores of definition files.

A store reads every ``*.hy`` file of an ordered list of directories ("layers",
lowest priority first, e.g. ``[global_dir, user_dir]``). A definition in a
higher layer overrides the same name in a lower one. Only the top layer is
writable: lower layers are never modified and their items are never copied up
unless explicitly overridden with :meth:`DefinitionStore.put`.

Every definition remembers the file it came from, so a save rewrites exactly
the files that changed (others keep their formatting byte-for-byte), keeps each
file's header comments and order, and deletes a file whose last item was removed.

An optional parse cache (``cache_dir``) stores the parsed data per file, keyed
by path, mtime and size, so unchanged files are not parsed again.
"""

import hashlib
import pickle
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, Union

from .converter import HyConverter, engine_converter
from .definitions import Definition, format_definition, header_comments, read_definitions

CACHE_VERSION = 1

PathLike = Union[str, Path]


class DefinitionStore:
    def __init__(
        self,
        layers: Iterable[PathLike],
        *,
        heads: Optional[Iterable[str]] = None,
        default_file: str = "default.hy",
        cache_dir: Optional[PathLike] = None,
        converter: HyConverter = engine_converter,
        code_values: bool = False,
    ):
        self.code_values = code_values  # True for type/trait files (code kept as Code)
        self.layers: List[Path] = [Path(p) for p in layers]
        if not self.layers:
            raise ValueError("a DefinitionStore needs at least one layer")
        self.heads = set(heads) if heads is not None else None
        self.default_file = _hy_name(default_file)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.converter = converter
        self._reset()

    # ------------------------------------------------------------------ state
    def _reset(self) -> None:
        # name -> {layer index: (file, definition)}
        self._candidates: Dict[str, Dict[int, Tuple[Path, Definition]]] = {}
        # file -> ordered names defined in it (writable layer files are kept up to date)
        self._file_names: Dict[Path, List[str]] = {}
        self._file_headers: Dict[Path, List[str]] = {}
        self._dirty: set = set()

    @property
    def writable_layer(self) -> int:
        return len(self.layers) - 1

    # ------------------------------------------------------------------ loading
    def load(self) -> "DefinitionStore":
        self._reset()
        for index, directory in enumerate(self.layers):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.hy")):
                definitions, header = self._read_file(path)
                self._file_headers[path] = header
                self._file_names[path] = []
                for definition in definitions:
                    self._candidates.setdefault(definition.name, {})[index] = (path, definition)
                    if definition.name not in self._file_names[path]:
                        self._file_names[path].append(definition.name)
        return self

    def _read_file(self, path: Path) -> Tuple[List[Definition], List[str]]:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, CACHE_VERSION,
               tuple(sorted(self.heads)) if self.heads else None, self.code_values)
        cache_file = None
        if self.cache_dir is not None:
            digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
            cache_file = self.cache_dir / f"{digest}.pkl"
            try:
                cached_key, definitions, header = pickle.loads(cache_file.read_bytes())
                if cached_key == key:
                    for definition in definitions:
                        definition.source_file = path
                    return definitions, header
            except Exception:
                pass  # missing, stale or corrupt cache: parse the file

        text = path.read_text(encoding="utf-8")
        definitions = read_definitions(text, heads=self.heads, converter=self.converter,
                                       source_name=str(path), code_values=self.code_values)
        for definition in definitions:
            definition.source_file = path
        header = header_comments(text)

        if cache_file is not None:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(pickle.dumps((key, definitions, header)))
            except Exception:
                pass  # caching is an optimisation only
        return definitions, header

    # ------------------------------------------------------------------ reading
    def get(self, name: str) -> Optional[Definition]:
        effective = self._effective(name)
        return effective[1] if effective else None

    def __contains__(self, name: str) -> bool:
        return name in self._candidates

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def names(self) -> List[str]:
        return list(self._candidates)

    def items(self) -> Iterator[Tuple[str, Definition]]:
        for name in self._candidates:
            yield name, self._effective(name)[1]

    def origin(self, name: str) -> Optional[Tuple[Path, int]]:
        candidates = self._candidates.get(name)
        if not candidates:
            return None
        layer = max(candidates)
        return candidates[layer][0], layer

    def names_in(self, file: PathLike) -> List[str]:
        """Names defined in a file (a bare file name refers to the writable layer)."""
        path = self._resolve_file(file)
        return list(self._file_names.get(path, []))

    def files(self, layer: Optional[int] = None) -> List[Path]:
        layer = self.writable_layer if layer is None else layer
        return [p for p in self._file_names if p.parent == self.layers[layer]]

    def _effective(self, name: str) -> Optional[Tuple[Path, Definition]]:
        candidates = self._candidates.get(name)
        return candidates[max(candidates)] if candidates else None

    def _resolve_file(self, file: PathLike) -> Path:
        path = Path(file)
        if path.parent == Path("."):
            path = self.layers[self.writable_layer] / _hy_name(str(path))
        return path

    # ------------------------------------------------------------------ writing
    def put(self, definition: Definition, file: Optional[PathLike] = None) -> None:
        """Add or replace a definition in the writable layer.

        Without ``file``, an item already in the writable layer stays in its file;
        anything else goes to the default file. With ``file``, it moves there.
        """
        top = self.writable_layer
        current = self._candidates.get(definition.name, {}).get(top)
        if file is not None:
            target = self._resolve_file(file)
        elif current is not None:
            target = current[0]
        else:
            target = self.layers[top] / self.default_file

        previous = self._effective(definition.name)
        if definition.symbol_name is None and previous is not None:
            definition.symbol_name = previous[1].symbol_name

        if current is not None and current[0] != target:
            self._file_names[current[0]].remove(definition.name)
            self._dirty.add(current[0])

        names = self._file_names.setdefault(target, [])
        if definition.name not in names:
            names.append(definition.name)
        definition.source_file = target
        self._candidates.setdefault(definition.name, {})[top] = (target, definition)
        self._dirty.add(target)

    def remove(self, name: str) -> bool:
        """Remove the writable-layer definition of ``name``.

        Returns False if there is none (items that only exist in lower layers
        cannot be removed). Removing an override reveals the lower definition.
        """
        candidates = self._candidates.get(name, {})
        entry = candidates.pop(self.writable_layer, None)
        if entry is None:
            return False
        self._file_names[entry[0]].remove(name)
        self._dirty.add(entry[0])
        if not candidates:
            del self._candidates[name]
        return True

    def save(self) -> None:
        """Rewrite every changed file of the writable layer."""
        top = self.writable_layer
        for path in sorted(self._dirty):
            names = self._file_names.get(path, [])
            if not names:
                if path.exists():
                    path.unlink()
                self._file_names.pop(path, None)
                continue
            blocks = [
                format_definition(self._candidates[name][top][1], self.converter, self.code_values)
                for name in names
            ]
            header = self._file_headers.get(path, [])
            text = ("\n".join(header) + "\n\n" if header else "") + "\n\n".join(blocks) + "\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._dirty.clear()


def _hy_name(name: str) -> str:
    return name if name.endswith(".hy") else f"{name}.hy"
