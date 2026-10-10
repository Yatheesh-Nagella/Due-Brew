import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# Optional free text: trimmed, and a blank string is stored as null.
OptionalText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None,
    AfterValidator(lambda v: v or None),
]


class NotifyMode(str, Enum):
    individual = "individual"
    digest = "digest"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tailscale_login: str
    display_name: str
    email: str
    notify_mode: NotifyMode
    digest_hour: int
    email_enabled: bool


class HealthOut(BaseModel):
    status: str
    db: str
    notifier_heartbeat_age_seconds: float | None


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


# --- categories ---


class CategoryCreate(BaseModel):
    name: Name
    sort_order: int | None = None


class CategoryUpdate(BaseModel):
    name: Name | None = None
    sort_order: int | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int


# --- items ---


class ItemStatus(str, Enum):
    needed = "needed"
    have = "have"
    low = "low"


Quantity = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class ItemCreate(BaseModel):
    name: Name
    category_id: uuid.UUID | None = None
    quantity: Quantity | None = None
    unit: OptionalText = None
    status: ItemStatus = ItemStatus.needed
    store: OptionalText = None
    notes: OptionalText = None


class ItemUpdate(BaseModel):
    """PATCH body: only the fields sent are changed; send null to clear one."""

    name: Name | None = None
    category_id: uuid.UUID | None = None
    quantity: Quantity | None = None
    unit: OptionalText = None
    status: ItemStatus | None = None
    store: OptionalText = None
    notes: OptionalText = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_id: uuid.UUID | None
    category: CategoryOut | None
    # float, not Decimal: pydantic would serialize Decimal as a JSON string.
    quantity: float | None
    unit: str | None
    status: ItemStatus
    store: str | None
    notes: str | None
    added_by_user: UserBrief
    updated_by_user: UserBrief
    created_at: datetime
    updated_at: datetime


class GroceryGroup(BaseModel):
    key: str | None  # category id or store name; null = uncategorized / no store
    label: str
    items: list[ItemOut]


class GroceryList(BaseModel):
    need_count: int
    low_count: int
    groups: list[GroceryGroup]
