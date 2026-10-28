"""Load and validate agent definitions from Markdown front matter."""

from dataclasses import dataclass
from pathlib import Path
import fnmatch


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    path: Path
    tools: tuple
    writable_paths: tuple
    skills: tuple


def _parse_front_matter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Agent definition must start with YAML front matter.")

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("Agent definition has no closing front matter marker.") from exc

    data = {}
    current_key = None

    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        stripped = line.strip()
        if line.startswith("  - ") and current_key:
            if not isinstance(data.get(current_key), list):
                raise ValueError(f"Invalid list value for '{current_key}'.")
            data[current_key].append(stripped[2:])
            continue

        if line.startswith("  ") and current_key:
            if isinstance(data.get(current_key), str):
                data[current_key] += " " + stripped
            else:
                raise ValueError(f"Unexpected continuation for '{current_key}'.")
            continue

        if ":" not in line:
            raise ValueError(f"Invalid front matter line: {line!r}")

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key

        if not key:
            raise ValueError("Front matter contains an empty key.")

        if not value:
            data[key] = []
        else:
            data[key] = value

    for key, value in list(data.items()):
        if isinstance(value, str) and value.strip() == "[]":
            data[key] = []
    return data


class AgentRegistry:
    """Read agent definitions without executing their contents."""

    def __init__(self, project_root=None):
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parent.parent
        )
        self.agents_dir = self.project_root / ".agents" / "agents"

    def list_agents(self) -> list:
        if not self.agents_dir.is_dir():
            raise FileNotFoundError(
                f"Agent definitions directory not found: {self.agents_dir}"
            )

        definitions = []
        for path in sorted(self.agents_dir.glob("*.md")):
            definitions.append(self._load_file(path))
        return definitions

    def get(self, name: str) -> AgentDefinition:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Agent name cannot be empty.")

        matches = [item for item in self.list_agents() if item.name == name]
        if not matches:
            raise ValueError(f"Unknown agent: {name}")
        if len(matches) > 1:
            raise ValueError(f"Duplicate agent name: {name}")
        return matches[0]

    def _load_file(self, path: Path) -> AgentDefinition:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ValueError(f"Cannot read agent definition: {path}") from exc

        data = _parse_front_matter(text)
        name = data.get("name")
        description = data.get("description", "")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Agent definition has no valid name: {path}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Agent definition has no valid description: {path}")

        def read_list(key):
            value = data.get(key, [])
            if not isinstance(value, list):
                raise ValueError(f"'{key}' must be a YAML-style list in {path}")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"'{key}' contains an invalid entry in {path}")
            return tuple(value)

        return AgentDefinition(
            name=name.strip(),
            description=description.strip(),
            path=path.resolve(),
            tools=read_list("tools"),
            writable_paths=read_list("writable_paths"),
            skills=read_list("skills"),
        )

    @staticmethod
    def permits_write(definition: AgentDefinition, relative_path: str) -> bool:
        normalized = relative_path.replace("\\", "/").lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            return False
        return any(
            fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/"))
            for pattern in definition.writable_paths
        )