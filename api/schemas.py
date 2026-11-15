from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOMAINS = (
    "concept", "composition", "hero", "camera", "lighting", "color",
    "styling", "performance", "realism", "effectiveness",
)
TreatmentName = Literal["Premium Polish", "Director's Cut", "Bold Reimagination"]
TREATMENTS = ("Premium Polish", "Director's Cut", "Bold Reimagination")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Brand(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    colors: str = Field(max_length=500)
    style: str = Field(max_length=500)
    hero: str = Field(max_length=500)
    copy_space: str = Field(max_length=500)
    lighting: str = Field(max_length=500)
    photography: str = Field(max_length=500)
    locked: str = Field(max_length=500)
    negative: str = Field(max_length=500)


OOREDOO = Brand(
    name="Ooredoo Oman",
    colors="Bright, airy neutrals and approximately 40% signature Ooredoo red, naturally integrated in the scene. Keep any subtle AI effects ice blue.",
    style="Premium high-key commercial lifestyle photography with sophisticated styling.",
    hero="Place the hero on the left.",
    copy_space="Reserve the right for headline copy. Continue the environment into this area with low visual contrast and clean depth.",
    lighting="Use physically coherent multi-source lighting, with a soft key, controlled fill and motivated edge separation.",
    photography="Vary focal lengths and angles according to the scene, scale and intended emphasis. Keep skin and materials natural.",
    locked="Preserve identity, product design and approved logo geometry and typography.",
    negative="Avoid unnecessary floating interfaces, heavy grading and unnatural red spill on skin.",
)


class AuditRequest(StrictModel):
    asset_id: UUID
    brief: str = Field(default="", max_length=4000)
    brand: Brand | None = None


class Finding(StrictModel):
    observation: str
    assumption: str
    recommendation: str
    rationale: str


class Review(StrictModel):
    concept: Finding
    composition: Finding
    hero: Finding
    camera: Finding
    lighting: Finding
    color: Finding
    styling: Finding
    performance: Finding
    realism: Finding
    effectiveness: Finding


class Priority(StrictModel):
    issue: str
    action: str
    rationale: str


class Treatment(StrictModel):
    name: TreatmentName
    direction: str
    rationale: str
    changes: list[str]
    preserve: list[str]
    avoid: list[str]
    execution: str


class Audit(StrictModel):
    verdict: str
    preserve: list[str]
    priorities: list[Priority]
    review: Review
    treatments: list[Treatment]

    @model_validator(mode="after")
    def validate_decisions(self):
        if tuple(item.name for item in self.treatments) != TREATMENTS:
            raise ValueError("Return each treatment exactly once in the prescribed order")
        if not 1 <= len(self.priorities) <= 5:
            raise ValueError("Return one to five ranked priorities")
        for item in self.treatments:
            if not (item.direction.strip() and item.execution.strip() and item.changes and item.preserve and item.avoid):
                raise ValueError("Each treatment needs actionable directions and preservation constraints")
        return self


class PromptRequest(StrictModel):
    treatment: TreatmentName
    text: str | None = Field(default=None, min_length=1, max_length=20000)


def assemble_prompt(audit: Audit, request: AuditRequest, name: TreatmentName) -> str:
    treatment = next(item for item in audit.treatments if item.name == name)
    changes = "\n".join(f"{index}. {change}" for index, change in enumerate(treatment.changes, 1))
    preservation = "\n".join(f"- {item}" for item in dict.fromkeys(audit.preserve + treatment.preserve))
    avoid = "\n".join(f"- {item}" for item in treatment.avoid)
    blocks = [
        f"Use the uploaded advertising image as the visual reference. Apply the {name} treatment.",
        f"CREATIVE INTENT\n{treatment.direction}",
        f"EDIT IN PRIORITY ORDER\n{changes}",
        f"PHOTOGRAPHIC EXECUTION\n{treatment.execution}",
        f"PRESERVE\n{preservation}",
        f"AVOID\n{avoid}",
    ]
    if request.brand:
        blocks.append(f"CAMPAIGN LOCKS AND EXCLUSIONS\n{request.brand.locked}\n{request.brand.negative}")
    blocks.append("Deliver one finished commercial image. Preserve the reference aspect ratio and all locked brand geometry. Keep the intended copy area usable and add no copy unless it was explicitly approved in the editing directions.")
    return "\n\n".join(blocks)
