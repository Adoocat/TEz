from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from tez.modules.settings.secrets import SecretName

Language = Literal["tr", "en"]
Theme = Literal["light", "dark", "system"]
# GROBID on this computer only (rule 1): the PDF goes to it.
GrobidUrl = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=100,
        pattern=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?/?$",
    ),
]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


class AppSettings(BaseModel):
    # None: follow the operating system's language.
    language: Language | None = None
    theme: Theme = "system"
    # Sent to Crossref and Unpaywall for their "polite pool" (plan, API terms).
    sources_email: Email | None = None
    # GROBID's address (Task 56); none: everything that needs it is hidden.
    grobid_url: GrobidUrl | None = None


class SettingsPatch(BaseModel):
    """Only the fields present are changed; null resets a field to its default."""

    model_config = ConfigDict(extra="forbid")

    language: Language | None = None
    theme: Theme | None = None
    sources_email: Email | None = None
    grobid_url: GrobidUrl | None = None


class SecretStatus(BaseModel):
    name: SecretName
    configured: bool


class SecretValue(BaseModel):
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
