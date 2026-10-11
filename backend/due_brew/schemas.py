import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

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


# --- bills ---


class Recurrence(str, Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"
    once = "once"


Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
DaysBefore = Annotated[int, Field(ge=0, le=30)]


def _unique_sorted_desc(values: list[int]) -> list[int]:
    return sorted(set(values), reverse=True)


class BillFields(BaseModel):
    """Everything about a bill except who it's assigned to and its reminders.
    Cross-field rules (yearly needs a month, once uses start_date) are applied
    in due_brew.api.routers.bills once defaults are filled in."""

    name: Name
    amount: Money | None = None
    recurrence: Recurrence
    due_day: int | None = Field(default=None, ge=1, le=31)
    due_month: int | None = Field(default=None, ge=1, le=12)
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True
    notes: OptionalText = None


class BillCreate(BillFields):
    assignee_ids: list[uuid.UUID] = Field(min_length=1)
    # Spec default: 3 days before and on the due date.
    reminder_days: list[DaysBefore] = Field(default_factory=lambda: [3, 0])

    _dedupe = field_validator("reminder_days")(_unique_sorted_desc)


class BillUpdate(BaseModel):
    """PATCH body: only the fields sent are changed."""

    name: Name | None = None
    amount: Money | None = None
    recurrence: Recurrence | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    due_month: int | None = Field(default=None, ge=1, le=12)
    start_date: date | None = None
    end_date: date | None = None
    active: bool | None = None
    notes: OptionalText = None
    assignee_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    reminder_days: list[DaysBefore] | None = None

    @field_validator("reminder_days")
    @classmethod
    def _dedupe(cls, values):
        return None if values is None else _unique_sorted_desc(values)


class OccurrenceOut(BaseModel):
    id: uuid.UUID
    bill_id: uuid.UUID
    bill_name: str
    due_date: date
    # The occurrence's own amount if set, else the bill's; null = "amount not set".
    amount: float | None
    variable: bool  # the bill has no fixed amount
    paid_at: datetime | None
    paid_by_user: UserBrief | None
    assignees: list[UserBrief]
    days_until: int  # negative = overdue by that many days
    state: str  # paid | overdue | due_today | upcoming


class BillOut(BaseModel):
    id: uuid.UUID
    name: str
    amount: float | None
    recurrence: Recurrence
    due_day: int
    due_month: int | None
    start_date: date
    end_date: date | None
    active: bool
    notes: str | None
    assignees: list[UserBrief]
    reminder_days: list[int]
    next_occurrence: OccurrenceOut | None
    paid_count: int


class OccurrenceUpdate(BaseModel):
    amount: Money | None
