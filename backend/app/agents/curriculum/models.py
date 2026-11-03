"""Validated curriculum and alignment contracts shared by all agents."""
from math import isclose
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator


Statement = Annotated[str, Field(min_length=1, max_length=2000)]


class ContentModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class Module(ContentModel):
    module_number: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=5, max_length=4000)
    topics: list[Statement] = Field(min_length=1, max_length=30)
    duration_hours: float = Field(gt=0, le=5000)
    learning_outcomes: list[Statement] = Field(min_length=1, max_length=30)
    activities: list[Statement] = Field(min_length=1, max_length=30)


class Exercise(ContentModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=5, max_length=4000)
    module: str = Field(min_length=1, max_length=500)
    type: str = Field(min_length=2, max_length=100)
    duration_hours: float = Field(gt=0, le=5000)


class Assessment(ContentModel):
    title: str = Field(min_length=2, max_length=300)
    type: str = Field(min_length=2, max_length=100)
    weight_percent: float = Field(gt=0, le=100)
    description: str = Field(min_length=5, max_length=4000)
    module: str = Field(min_length=1, max_length=500)


class Capstone(ContentModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=5, max_length=6000)
    deliverables: list[Statement] = Field(min_length=1, max_length=30)
    evaluation_criteria: list[Statement] = Field(min_length=1, max_length=30)
    duration_hours: float = Field(gt=0, le=5000)


class CurriculumContent(ContentModel):
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=10, max_length=10000)
    objectives: list[Statement] = Field(min_length=1, max_length=30)
    prerequisites: list[Statement] = Field(max_length=30)
    learning_outcomes: list[Statement] = Field(min_length=1, max_length=30)
    modules: list[Module] = Field(min_length=1, max_length=50)
    training_hours: float = Field(gt=0, le=5000)
    practical_exercises: list[Exercise] = Field(min_length=1, max_length=50)
    assessments: list[Assessment] = Field(min_length=1, max_length=30)
    capstone_project: Capstone

    @model_validator(mode="after")
    def consistent_plan(self):
        if not isclose(sum(a.weight_percent for a in self.assessments), 100, abs_tol=.01):
            raise ValueError("Assessment weights must total 100 percent")
        if not isclose(sum(m.duration_hours for m in self.modules), self.training_hours, abs_tol=.01):
            raise ValueError("Module hours must equal total training hours")
        if [m.module_number for m in self.modules] != list(range(1, len(self.modules) + 1)):
            raise ValueError("Modules must be numbered sequentially")
        if any(not s.strip() for s in self.objectives + self.learning_outcomes + self.prerequisites):
            raise ValueError("Learning statements must not be empty")
        if self.capstone_project.duration_hours > self.training_hours:
            raise ValueError("Capstone duration exceeds course hours")
        if sum(e.duration_hours for e in self.practical_exercises) > self.training_hours:
            raise ValueError("Exercise duration exceeds course hours")
        return self


class Competency(ContentModel):
    competency: str = Field(min_length=2, max_length=2000)
    status: Literal["fully_aligned", "partially_aligned", "not_addressed"]
    curriculum_coverage: str = Field(max_length=4000)
    gaps: str = Field(max_length=4000)
    recommendation: str = Field(max_length=4000)


class Alignment(ContentModel):
    framework_name: str = Field(min_length=2, max_length=300)
    overall_alignment_score: float = Field(ge=0, le=100)
    summary: str = Field(min_length=5, max_length=6000)
    competency_alignment: list[Competency] = Field(min_length=1, max_length=100)
    missing_topics: list[Statement] = Field(max_length=100)
    strengths: list[Statement] = Field(max_length=100)
    recommendations: list[Statement] = Field(max_length=100)
    disclaimer: str = "Automated proposed alignment only. This does not confer official accreditation."
