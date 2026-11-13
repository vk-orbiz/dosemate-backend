"""Scaffold a user-owned CRUD API that follows the layered architecture (see agent.md).

    uv run python scripts/make_api.py todo --fields "title:str description:str? done:bool"
    uv run python scripts/make_api.py todo --dry-run
    uv run python scripts/make_api.py todo --wire

The CLI owns structure: it writes the new per-layer files (model, entity, repo, service,
dto, validators, handler, routes, plus a unit and an integration test). The shared files
(errors, tables, migration, protocols, deps, main, server) are edited by `--wire`, or you
get the exact snippets to paste. You and your agent own the business logic; tests own
enforcement.

Field syntax: `name:type`, type one of str, int, bool, float; append `?` for optional
(`description:str?`). Default when `--fields` is omitted: `name:str`.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import keyword
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"

# (template file, output path relative to the repo root; `{name}` is the snake_case name)
FILES: tuple[tuple[str, str], ...] = (
    ("model.py.tmpl", "app/models/{name}.py"),
    ("entity.py.tmpl", "app/repo/entities/{name}.py"),
    ("repo.py.tmpl", "app/repo/{name}.py"),
    ("service.py.tmpl", "app/service/{name}.py"),
    ("dto.py.tmpl", "app/transport/http/dto/{name}.py"),
    ("validators.py.tmpl", "app/transport/http/validators/{name}.py"),
    ("handler.py.tmpl", "app/transport/http/handlers/{name}.py"),
    ("routes.py.tmpl", "app/transport/http/routes/{name}.py"),
    ("test_service.py.tmpl", "tests/unit/test_{name}_service.py"),
    ("test_endpoints.py.tmpl", "tests/integration/test_{name}_endpoints.py"),
)

MAX_NAME_LEN = 30
RESERVED_NAMES = frozenset(
    {"auth", "user", "users", "general", "health", "common", "error", "errors", "config", "main"}
)
RESERVED_FIELDS = frozenset({"id", "user_id", "created_at", "updated_at"})
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_SQL_TYPES = {"str": "text", "int": "bigint", "bool": "boolean", "float": "double precision"}


class ScaffoldError(ValueError):
    """Bad input or an unsafe target; the message is shown to the user as is."""


# --- naming -----------------------------------------------------------------------------


def to_snake(raw: str) -> str:
    """`TodoItem`, `todo-item` and `todo item` all become `todo_item`."""
    spaced = re.sub(r"[-\s]+", "_", raw.strip())
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", spaced).lower()


def to_pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


def pluralize(name: str) -> str:
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    if name.endswith("y") and len(name) > 1 and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def validate_identifier(value: str, what: str, *, allow_builtins: bool = False) -> str:
    if not _IDENT.match(value):
        raise ScaffoldError(f"{what} {value!r} must match [a-z][a-z0-9_]* (snake_case)")
    if keyword.iskeyword(value) or (not allow_builtins and hasattr(builtins, value)):
        raise ScaffoldError(f"{what} {value!r} is a Python keyword or builtin")
    if len(value) > MAX_NAME_LEN:
        raise ScaffoldError(f"{what} {value!r} is longer than {MAX_NAME_LEN} characters")
    return value


# --- fields -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    name: str
    py: str  # str | int | bool | float
    optional: bool

    @property
    def pytype(self) -> str:
        return f"{self.py} | None" if self.optional else self.py

    @property
    def sql(self) -> str:
        return _SQL_TYPES[self.py] + ("" if self.optional else " NOT NULL")


def parse_fields(spec: str) -> list[Field]:
    tokens = [t for t in re.split(r"[,\s]+", spec.strip()) if t] or ["name:str"]
    fields: list[Field] = []
    for token in tokens:
        name, sep, type_part = token.partition(":")
        if not sep or not type_part:
            raise ScaffoldError(f"field {token!r} must look like name:type (e.g. title:str)")
        optional = type_part.endswith("?")
        py = type_part.rstrip("?")
        if py not in _SQL_TYPES:
            raise ScaffoldError(f"field {name!r}: type {py!r} not in {sorted(_SQL_TYPES)}")
        validate_identifier(name, "field name", allow_builtins=True)
        if name in RESERVED_FIELDS:
            raise ScaffoldError(f"field name {name!r} is generated automatically")
        if any(f.name == name for f in fields):
            raise ScaffoldError(f"duplicate field {name!r}")
        fields.append(Field(name, py, optional))
    return fields


def _sample(f: Field, *, updated: bool) -> object:
    if f.py == "str":
        return f"{'updated' if updated else 'example'} {f.name.replace('_', ' ')}"
    if f.py == "int":
        return 2 if updated else 1
    if f.py == "bool":
        return not updated
    return 2.5 if updated else 1.5


# --- template context -------------------------------------------------------------------


def _lines(items: list[str]) -> str:
    return "\n".join(items)


def _dto_field(f: Field) -> str:
    if f.py == "str":
        if f.optional:
            return f"{f.name}: str | None = Field(default=None, max_length=255)"
        return f"{f.name}: str = Field(min_length=1, max_length=255)"
    return f"{f.name}: {f.pytype} = None" if f.optional else f"{f.name}: {f.py}"


def _validation(f: Field) -> list[str]:
    if f.py != "str":
        return []
    if f.optional:
        return [f'{f.name} = (dto.{f.name} or "").strip() or None']
    return [
        f"{f.name} = dto.{f.name}.strip()",
        f"if not {f.name}:",
        f'    raise InvalidInput("{f.name} must not be blank")',
    ]


def build_context(name: str, plural: str, fields: list[Field], version: int) -> dict[str, str]:
    n = [f.name for f in fields]
    first = fields[0]
    return {
        "name": name,
        "Name": to_pascal(name),
        "plural": plural,
        "PLURAL": plural.upper(),
        "version": str(version),
        "first_field": first.name,
        "model_fields": _lines([f"{f.name}: {f.pytype}" for f in fields]),
        "record_kwargs": _lines([f'{x}=record["{x}"],' for x in n]),
        "from_model_kwargs": _lines([f"{x}={name}.{x}," for x in n]),
        "to_model_kwargs": _lines([f"{x}=self.{x}," for x in n]),
        "draft_to_model_kwargs": _lines([f"{x}=draft.{x}," for x in n]),
        "columns_quoted": ", ".join(f'"{x}"' for x in n),
        "insert_placeholders": ", ".join(f"${i}" for i in range(1, len(n) + 5)),
        "update_set": _lines([f"{x} = ${i}," for i, x in enumerate(n, start=3)]),
        "updated_at_param": str(len(n) + 3),
        "entity_args": ", ".join(f"e.{x}" for x in n),
        "draft_args": ", ".join(f"draft.{x}" for x in n),
        "request_fields": _lines([_dto_field(f) for f in fields]),
        "response_fields": _lines([f"{f.name}: {f.pytype}" for f in fields]),
        "validation_lines": _lines([line for f in fields for line in _validation(f)]),
        "draft_kwargs": _lines(
            [f"{f.name}={f.name}," if f.py == "str" else f"{f.name}=dto.{f.name}," for f in fields]
        ),
        "response_kwargs": _lines([f"{x}={name}.{x}," for x in n]),
        "migration_columns": _lines([f"{f.name} {f.sql}," for f in fields]),
        "sample_kwargs": _lines([f"{f.name}={_sample(f, updated=False)!r}," for f in fields]),
        "updated_kwargs": _lines([f"{f.name}={_sample(f, updated=True)!r}," for f in fields]),
        "payload_sample": _lines([f'"{f.name}": {_sample(f, updated=False)!r},' for f in fields]),
        "payload_updated": _lines([f'"{f.name}": {_sample(f, updated=True)!r},' for f in fields]),
    }


_BLOCK = re.compile(r"^([ \t]*)\{\{(\w+)\}\}[ \t]*$")
_INLINE = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, ctx: dict[str, str]) -> str:
    """Replace `{{key}}`. A token alone on a line expands to several lines at that indent
    (and the line is dropped when the value is empty). Unknown keys raise KeyError."""
    out: list[str] = []
    for line in template.split("\n"):
        block = _BLOCK.match(line)
        if block:
            indent, key = block.groups()
            out.extend(indent + part for part in ctx[key].split("\n") if ctx[key])
        else:
            out.append(_INLINE.sub(lambda m: ctx[m.group(1)], line))
    return "\n".join(out)


# --- repo inspection --------------------------------------------------------------------


def next_migration_version(root: Path) -> int:
    """Highest version in `_MIGRATIONS` plus one (1 if the file or tuple is missing)."""
    db_file = root / "app/storage/postgres/db.py"
    if not db_file.exists():
        return 1
    versions: list[int] = []
    for node in ast.walk(ast.parse(db_file.read_text())):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names, value = [node.target.id], node.value
        elif isinstance(node, ast.Assign):
            names, value = [t.id for t in node.targets if isinstance(t, ast.Name)], node.value
        else:
            continue
        if "_MIGRATIONS" in names and isinstance(value, ast.Tuple):
            for item in value.elts:
                if isinstance(item, ast.Tuple) and item.elts:
                    first = item.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, int):
                        versions.append(first.value)
    return max(versions, default=0) + 1


def _already_wired(root: Path, name: str, plural: str) -> list[str]:
    hits: list[str] = []
    errors = root / "app/core/errors.py"
    if errors.exists() and f"class {to_pascal(name)}NotFound" in errors.read_text():
        hits.append("app/core/errors.py already defines it")
    tables = root / "app/storage/postgres/tables.py"
    if tables.exists() and re.search(rf"^{plural.upper()}\s*=", tables.read_text(), re.M):
        hits.append("app/storage/postgres/tables.py already has the table constant")
    return hits


# --- wiring the shared files ------------------------------------------------------------

# (file, import lines to add, template sections). Imports are sorted by ruff afterwards.
WIRING: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("app/core/errors.py", (), ("errors",)),
    ("app/storage/postgres/tables.py", (), ("tables",)),
    ("app/storage/postgres/db.py", (), ("migration",)),
    (
        "app/service/protocols.py",
        (
            "from datetime import datetime",
            "from uuid import UUID",
            "from app.models.{{name}} import {{Name}}, {{Name}}Draft",
        ),
        ("service_protocol",),
    ),
    (
        "app/transport/http/protocols.py",
        ("from app.models.{{name}} import {{Name}}, {{Name}}Draft",),
        ("http_protocol",),
    ),
    (
        "app/transport/http/deps.py",
        ("from app.transport.http.handlers.{{name}} import {{Name}}Handler",),
        ("deps",),
    ),
    (
        "app/main.py",
        (
            "from app.repo.{{name}} import {{Name}}Repo",
            "from app.service.{{name}} import {{Name}}Service",
            "from app.transport.http.handlers.{{name}} import {{Name}}Handler",
        ),
        ("main_build", "main_state"),
    ),
    (
        "app/transport/http/server.py",
        ("from app.transport.http.routes import {{name}}",),
        ("include_router",),
    ),
)


def _sections(ctx: dict[str, str]) -> dict[str, str]:
    """Split wiring.tmpl into its `### key` sections, rendered."""
    sections: dict[str, list[str]] = {}
    current: list[str] = []
    for line in (TEMPLATES / "wiring.tmpl").read_text().split("\n"):
        if line.startswith("### "):
            current = sections.setdefault(line[4:].strip(), [])
        else:
            current.append(line)
    return {key: render("\n".join(lines).strip("\n"), ctx) for key, lines in sections.items()}


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.split("\n"))


def render_wiring_text(ctx: dict[str, str]) -> str:
    """Human-readable version of the edits `--wire` would make."""
    sections = _sections(ctx)
    out = ["Wire the shared files by hand (or re-run with --wire):", ""]
    for number, (path, imports, keys) in enumerate(WIRING, start=1):
        out.append(f"{number}. {path}")
        out.extend(f"     import: {render(line, ctx)}" for line in imports)
        for key in keys:
            out.append(_indent(sections[key], "     "))
    out += [
        "",
        f"app/transport/http/error_map.py: nothing to do ({ctx['Name']}NotFound inherits "
        "NotFound -> 404).",
        "",
        "Then: uv run ruff check . && uv run ruff format . && uv run mypy app && uv run pytest",
    ]
    return "\n".join(out)


def _add_imports(path: str, text: str, lines: list[str]) -> str:
    new = [line for line in lines if line not in text]
    if not new:
        return text
    tree = ast.parse(text)
    ends = [n.end_lineno for n in tree.body if isinstance(n, ast.Import | ast.ImportFrom)]
    at = max((e for e in ends if e), default=0)
    if not at:
        raise ScaffoldError(f"cannot wire {path}: no import block found")
    parts = text.split("\n")
    return "\n".join([*parts[:at], *new, *parts[at:]])


def _migrations_tuple(text: str) -> ast.Tuple | None:
    for node in ast.parse(text).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        if "_MIGRATIONS" in names and isinstance(node.value, ast.Tuple):
            return node.value
    return None


def _insert_migration(text: str, block: str) -> str:
    value = _migrations_tuple(text)
    lines = text.split("\n")
    if value is None or value.end_lineno is None or lines[value.end_lineno - 1].strip() != ")":
        raise ScaffoldError("cannot wire app/storage/postgres/db.py: _MIGRATIONS tuple not found")
    at = value.end_lineno - 1
    lines[at:at] = _indent(block, "    ").split("\n")
    return "\n".join(lines)


def _insert_before(path: str, text: str, pattern: str, block: str) -> str:
    match = re.search(pattern, text, re.M)
    if not match:
        raise ScaffoldError(f"cannot wire {path}: anchor {pattern!r} not found")
    return text[: match.start()] + block + text[match.start() :]


def plan_wiring(root: Path, ctx: dict[str, str]) -> dict[Path, str]:
    """New contents for every shared file, computed in memory (nothing is written)."""
    sections = _sections(ctx)
    plan: dict[Path, str] = {}
    for rel, imports, keys in WIRING:
        path = root / rel
        if not path.exists():
            raise ScaffoldError(f"cannot wire {rel}: file not found")
        text = path.read_text()
        block = "\n\n".join(sections[k] for k in keys)
        if rel.endswith("db.py"):
            text = _insert_migration(text, sections["migration"])
        elif rel.endswith("tables.py"):
            text = text.rstrip("\n") + "\n" + block + "\n"
        elif rel.endswith("main.py"):
            build, state = _indent(sections["main_build"], "    "), sections["main_state"]
            text = _insert_before(rel, text, r"^    @asynccontextmanager$", build + "\n\n")
            text = _insert_before(rel, text, r"^    return app$", _indent(state, "    ") + "\n")
        elif rel.endswith("server.py"):
            text = _wire_server(text, ctx["name"], sections["include_router"])
        else:
            text = text.rstrip("\n") + "\n\n\n" + block + "\n"
        if not rel.endswith("server.py"):
            text = _add_imports(rel, text, [render(i, ctx) for i in imports])
        plan[path] = text
    return plan


def _wire_server(text: str, name: str, include: str) -> str:
    pattern = r"^(from app\.transport\.http\.routes import )(.+)$"
    if not re.search(pattern, text, re.M):
        raise ScaffoldError("cannot wire server.py: routes import not found")
    text = re.sub(pattern, rf"\1\2, {name}", text, count=1, flags=re.M)
    matches = list(re.finditer(r"^    app\.include_router\(.*\)$", text, re.M))
    if not matches:
        raise ScaffoldError("cannot wire server.py: no include_router call found")
    end = matches[-1].end()
    return text[:end] + "\n" + _indent(include, "    ") + text[end:]


# --- scaffolding ------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    written: list[Path]
    overwritten: list[Path]
    modified: list[Path]  # shared files changed by --wire
    wiring: str
    dry_run: bool


def scaffold(
    raw_name: str,
    *,
    plural: str | None = None,
    fields_spec: str = "",
    root: Path = ROOT,
    dry_run: bool = False,
    force: bool = False,
    wire: bool = False,
    format_code: bool = True,
) -> Result:
    name = validate_identifier(to_snake(raw_name), "name")
    plural_name = validate_identifier(plural or pluralize(name), "plural")
    for value in (name, plural_name):
        if value in RESERVED_NAMES:
            raise ScaffoldError(f"{value!r} is reserved by the existing code base")
    fields = parse_fields(fields_spec)

    targets = [(tmpl, root / rel.format(name=name)) for tmpl, rel in FILES]
    existing = [p for _, p in targets if p.exists()]
    if existing and not force:
        listing = "\n  ".join(str(p.relative_to(root)) for p in existing)
        raise ScaffoldError(f"refusing to overwrite (use --force):\n  {listing}")
    if not force and (wired := _already_wired(root, name, plural_name)):
        raise ScaffoldError("looks already wired: " + "; ".join(wired) + " (use --force)")

    ctx = build_context(name, plural_name, fields, next_migration_version(root))
    rendered = [(path, render((TEMPLATES / tmpl).read_text(), ctx)) for tmpl, path in targets]
    wiring = render_wiring_text(ctx)
    shared = plan_wiring(root, ctx) if wire else {}  # raises before anything is written

    if not dry_run:
        for path, text in [*rendered, *shared.items()]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        if format_code:
            _tidy([*(p for p, _ in rendered), *shared], root)
    return Result(
        written=[p for _, p in targets if p not in existing],
        overwritten=existing,
        modified=list(shared),
        wiring=wiring,
        dry_run=dry_run,
    )


def _tidy(paths: list[Path], root: Path) -> None:
    """Best effort: drop unused imports, sort imports, format (needs ruff in the venv)."""
    config = (
        ["--config", str(root / "pyproject.toml")] if (root / "pyproject.toml").exists() else []
    )
    files = [str(p) for p in paths]
    steps = (
        ["check", "--select", "F401,I", "--fix", "--quiet", *config, *files],
        ["format", "--quiet", *config, *files],
    )
    for step in steps:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", *step], capture_output=True, text=True, check=False
        )
        if "No module named ruff" in proc.stderr:
            print("note: ruff not installed; run `uv run ruff format .` yourself", file=sys.stderr)
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("name", help="singular resource name, e.g. todo or todo_item")
    parser.add_argument("--plural", help="override the plural used for table and URL")
    parser.add_argument("--fields", default="", help='e.g. "title:str description:str? done:bool"')
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would happen, write nothing"
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument(
        "--wire", action="store_true", help="also edit the shared files (errors, db, main, ...)"
    )
    args = parser.parse_args(argv)

    try:
        result = scaffold(
            args.name,
            plural=args.plural,
            fields_spec=args.fields,
            dry_run=args.dry_run,
            force=args.force,
            wire=args.wire,
        )
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verb = "would create" if result.dry_run else "created"
    for path in result.written:
        print(f"{verb}  {path.relative_to(ROOT)}")
    for path in result.overwritten:
        print(f"{'would overwrite' if result.dry_run else 'overwrote'}  {path.relative_to(ROOT)}")
    for path in result.modified:
        print(f"{'would modify' if result.dry_run else 'modified'}  {path.relative_to(ROOT)}")
    print()
    if result.modified:
        print("Shared files wired. Now: uv run ruff check . && uv run mypy app && uv run pytest")
    else:
        print(result.wiring)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
