"""The `scripts/make_api.py` scaffolder: naming, safety rules and sane generated code."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import make_api
from scripts.make_api import ScaffoldError, scaffold


@pytest.fixture
def root(tmp_path: Path) -> Path:
    db = tmp_path / "app/storage/postgres/db.py"
    db.parent.mkdir(parents=True)
    db.write_text('_MIGRATIONS: tuple[tuple[int, str], ...] = (\n    (1, "a"),\n    (2, "b"),\n)\n')
    return tmp_path


def test_naming_conversions() -> None:
    assert make_api.to_snake("TodoItem") == "todo_item"
    assert make_api.to_snake("todo-item") == "todo_item"
    assert make_api.to_snake(" Todo ") == "todo"
    assert make_api.to_pascal("todo_item") == "TodoItem"
    assert make_api.pluralize("todo") == "todos"
    assert make_api.pluralize("category") == "categories"
    assert make_api.pluralize("day") == "days"
    assert make_api.pluralize("box") == "boxes"
    assert make_api.pluralize("status") == "statuses"


@pytest.mark.parametrize("bad", ["", "1todo", "to do!", "class", "list", "x" * 31])
def test_invalid_names_are_rejected(bad: str, root: Path) -> None:
    with pytest.raises(ScaffoldError):
        scaffold(bad, root=root, dry_run=True)


@pytest.mark.parametrize("reserved", ["user", "auth", "health"])
def test_reserved_names_are_rejected(reserved: str, root: Path) -> None:
    with pytest.raises(ScaffoldError, match="reserved"):
        scaffold(reserved, root=root, dry_run=True)


def test_parse_fields() -> None:
    fields = make_api.parse_fields("title:str, description:str? done:bool price:float count:int?")
    assert [(f.name, f.py, f.optional) for f in fields] == [
        ("title", "str", False),
        ("description", "str", True),
        ("done", "bool", False),
        ("price", "float", False),
        ("count", "int", True),
    ]
    assert [f.name for f in make_api.parse_fields("")] == ["name"]


@pytest.mark.parametrize(
    "bad", ["title", "title:", "title:date", "id:str", "a:str a:int", "Bad:str"]
)
def test_invalid_fields_are_rejected(bad: str) -> None:
    with pytest.raises(ScaffoldError):
        make_api.parse_fields(bad)


def test_next_migration_version(root: Path, tmp_path: Path) -> None:
    assert make_api.next_migration_version(root) == 3
    assert make_api.next_migration_version(tmp_path / "missing") == 1


def test_dry_run_writes_nothing(root: Path) -> None:
    result = scaffold("todo", root=root, dry_run=True)

    assert len(result.written) == len(make_api.FILES)
    assert not (root / "app/models").exists()
    assert "TodoNotFound" in result.wiring
    assert "TODOS" in result.wiring


def test_generates_every_file_with_no_leftover_tokens(root: Path) -> None:
    result = scaffold("todo_item", fields_spec="title:str done:bool", root=root, format_code=False)

    assert {p.relative_to(root).as_posix() for p in result.written} == {
        "app/models/todo_item.py",
        "app/repo/entities/todo_item.py",
        "app/repo/todo_item.py",
        "app/service/todo_item.py",
        "app/transport/http/dto/todo_item.py",
        "app/transport/http/validators/todo_item.py",
        "app/transport/http/handlers/todo_item.py",
        "app/transport/http/routes/todo_item.py",
        "tests/unit/test_todo_item_service.py",
        "tests/integration/test_todo_item_endpoints.py",
    }
    for path in result.written:
        text = path.read_text()
        ast.parse(text)
        assert "{{" not in text, path
    assert (
        'prefix="/v1/todo_items"' in (root / "app/transport/http/routes/todo_item.py").read_text()
    )
    assert "    3,\n" in result.wiring  # next migration version after 1 and 2


def test_refuses_to_overwrite_and_leaves_files_untouched(root: Path) -> None:
    scaffold("todo", root=root, format_code=False)
    model = root / "app/models/todo.py"
    model.write_text("# edited by hand\n")

    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        scaffold("todo", root=root, format_code=False)
    assert model.read_text() == "# edited by hand\n"

    result = scaffold("todo", root=root, force=True, format_code=False)
    assert model in result.overwritten
    assert "# edited by hand" not in model.read_text()


def test_refuses_when_already_wired(root: Path) -> None:
    errors = root / "app/core/errors.py"
    errors.parent.mkdir(parents=True)
    errors.write_text("class TodoNotFound(Exception): ...\n")

    with pytest.raises(ScaffoldError, match="already wired"):
        scaffold("todo", root=root, dry_run=True)


@pytest.mark.parametrize(
    "spec",
    [
        "title:str description:str? done:bool",
        "rank:int",
        "price:float? flag:bool?",
        "a:str b:str c:str d:str e:str f:str g:str h:str",
    ],
)
def test_generated_code_has_no_undefined_or_unused_names(spec: str, root: Path) -> None:
    result = scaffold("thing", fields_spec=spec, root=root)  # runs the ruff tidy-up

    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F,E9", "--no-cache", "--isolated"]
        + [str(p) for p in result.written],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_reports_errors_with_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert make_api.main(["Bad Name!"]) == 2
    assert "error:" in capsys.readouterr().err


def test_wire_failure_writes_nothing(root: Path) -> None:
    # `root` has db.py but none of the other shared files, so wiring cannot succeed.
    with pytest.raises(ScaffoldError, match="cannot wire"):
        scaffold("todo", root=root, wire=True, format_code=False)
    assert not (root / "app/models").exists()
