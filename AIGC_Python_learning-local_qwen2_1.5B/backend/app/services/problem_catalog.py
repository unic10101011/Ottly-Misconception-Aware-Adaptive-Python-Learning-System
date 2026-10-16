"""Validated, server-owned curriculum. No learner or model can edit this catalog."""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

SCHEMA_VERSION = '1.0.0'
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
LEGACY_IDS = {'level1', 'level2'}


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TestCase(CatalogModel):
    case_id: str = Field(min_length=1)
    expected_output: str
    stdin: str = Field(default='', max_length=8000)
    visibility: Literal['public', 'hidden'] = 'public'


class Problem(BaseModel):
    """Original execution/model-input shape, deliberately kept stable."""
    problem_id: str
    title: str
    description: str
    tests: list[TestCase]
    comparison: Literal['legacy_trim', 'exact'] = 'legacy_trim'


class Knowledge(CatalogModel):
    knowledge_id: str = Field(pattern=r'^K\d{2}$')
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class Teaching(CatalogModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    example: str


class Example(CatalogModel):
    stdin: str
    stdout: str


class LessonHints(CatalogModel):
    level1: str = Field(min_length=1)
    level2: str = Field(min_length=1)
    level3: str = Field(min_length=1)


class Lesson(CatalogModel):
    schema_version: Literal['1.0.0']
    problem_id: str = Field(min_length=1, max_length=100)
    version: int = Field(strict=True, ge=1)
    level_no: int = Field(strict=True, ge=1, le=12)
    title: str = Field(min_length=1, max_length=255)
    difficulty: Literal[1, 2, 3]
    knowledge_ids: list[str] = Field(min_length=1)
    prerequisite_knowledge_ids: list[str]
    prerequisite_problem_ids: list[str]
    published: bool
    story: str = Field(min_length=1)
    teaching: list[Teaching] = Field(min_length=1)
    description: str = Field(min_length=1)
    starter_code: str = Field(max_length=6000)
    examples: list[Example] = Field(min_length=1)
    tests: list[TestCase] = Field(min_length=1)
    comparison: Literal['legacy_trim', 'exact']
    time_limit_seconds: Literal[3]
    output_limit_chars: Literal[8000]
    hints: LessonHints
    reference_solution: str = Field(min_length=1, max_length=6000)
    solution_explanation: str = Field(min_length=1)

    @field_validator('difficulty', 'time_limit_seconds', 'output_limit_chars', mode='before')
    @classmethod
    def integer_limits(cls, value):
        if type(value) is not int:
            raise ValueError('expected an integer, not a boolean or string')
        return value

    @model_validator(mode='after')
    def consistent(self):
        if self.problem_id not in LEGACY_IDS:
            match = re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v([1-9]\d*)', self.problem_id)
            if not match or int(match[1]) != self.version:
                raise ValueError('problem_id must end with its version, e.g. greeting-v1')
            if self.comparison != 'exact':
                raise ValueError('new problems require exact comparison')
        for field in ('knowledge_ids', 'prerequisite_knowledge_ids', 'prerequisite_problem_ids'):
            values = getattr(self, field)
            if len(values) != len(set(values)):
                raise ValueError(f'duplicate {field}')
        ids = [test.case_id for test in self.tests]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate case_id')
        if self.problem_id not in LEGACY_IDS and not any(t.visibility == 'public' for t in self.tests):
            raise ValueError('a published input lesson needs a public test')
        if self.problem_id not in LEGACY_IDS and any(t.stdin for t in self.tests) and not any(t.visibility == 'hidden' for t in self.tests):
            raise ValueError('an input lesson needs a hidden test')
        return self

    def execution_problem(self) -> Problem:
        return Problem(**self.model_dump(include={'problem_id', 'title', 'description', 'tests', 'comparison'}))


class LevelSlot(CatalogModel):
    id: int = Field(ge=1, le=12)
    problem_id: str | None
    name: str = Field(min_length=1)
    prerequisite_problem_ids: list[str] = Field(default_factory=list)


def alias_key(text: str) -> str:
    return text.strip().casefold()


def validate_catalog(problems: dict[str, Lesson], knowledge: dict[str, Knowledge], levels: list[LevelSlot]):
    aliases = {}
    for item in knowledge.values():
        for name in [item.name, *item.aliases]:
            key = alias_key(name)
            if not key or (key in aliases and aliases[key] != item.knowledge_id):
                raise ValueError(f'empty or ambiguous knowledge alias: {name}')
            aliases[key] = item.knowledge_id
    for lesson in problems.values():
        if any(key not in knowledge for key in [*lesson.knowledge_ids, *lesson.prerequisite_knowledge_ids]):
            raise ValueError(f'{lesson.problem_id}: unknown knowledge ID')
        if any(key not in problems for key in lesson.prerequisite_problem_ids):
            raise ValueError(f'{lesson.problem_id}: unknown prerequisite problem')
    visited, visiting = set(), set()

    def visit(key):
        if key in visiting:
            raise ValueError(f'cyclic prerequisite: {key}')
        if key in visited:
            return
        visiting.add(key)
        for prerequisite in problems[key].prerequisite_problem_ids:
            visit(prerequisite)
        visiting.remove(key)
        visited.add(key)

    for key in problems:
        visit(key)
    if len({slot.id for slot in levels}) != len(levels):
        raise ValueError('duplicate level slot')
    active_ids = [slot.problem_id for slot in levels if slot.problem_id is not None]
    if len(active_ids) != len(set(active_ids)):
        raise ValueError('a problem cannot occupy two active levels')
    for slot in levels:
        if slot.problem_id is not None:
            if slot.problem_id not in problems or problems[slot.problem_id].level_no != slot.id:
                raise ValueError('level slot refers to an unknown/mismatched problem')
            if slot.prerequisite_problem_ids:
                raise ValueError('configured levels must use the lesson prerequisites')
        elif len(slot.prerequisite_problem_ids) != len(set(slot.prerequisite_problem_ids)) or any(key not in problems for key in slot.prerequisite_problem_ids):
            raise ValueError('invalid pending-level prerequisites')
    return aliases


def load_catalog(directory: Path = DATA_DIR):
    entries = [Knowledge.model_validate(item) for item in json.loads((directory / 'knowledge.json').read_text(encoding='utf-8'))]
    knowledge = {item.knowledge_id: item for item in entries}
    if len(knowledge) != len(entries):
        raise ValueError('duplicate knowledge ID')
    problems = {}
    for path in sorted(directory.glob('*.json')):
        if path.name in {'knowledge.json', 'levels.json'}:
            continue
        lesson = Lesson.model_validate_json(path.read_text(encoding='utf-8'))
        if lesson.problem_id in problems:
            raise ValueError(f'duplicate problem ID: {lesson.problem_id}')
        problems[lesson.problem_id] = lesson
    if not problems:
        raise ValueError('empty catalog')
    levels = [LevelSlot.model_validate(item) for item in json.loads((directory / 'levels.json').read_text(encoding='utf-8'))]
    aliases = validate_catalog(problems, knowledge, levels)
    return problems, knowledge, levels, aliases


PROBLEMS, KNOWLEDGE, LEVELS, KNOWLEDGE_ALIASES = load_catalog()
GREETING_ID = 'greeting-v1'
GREETING = PROBLEMS[GREETING_ID].model_dump()
