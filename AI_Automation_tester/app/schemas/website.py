from pydantic import BaseModel, Field


class WebsiteLink(BaseModel):
    text: str = ""
    url: str = ""
    element_type: str = "link"


class WebsiteButton(BaseModel):
    text: str = ""
    element_type: str = "button"


class WebsiteInput(BaseModel):
    name: str = ""
    input_type: str = "text"
    placeholder: str = ""
    required: bool = False


class WebsiteHeading(BaseModel):
    text: str = ""
    level: int = 0


class WebsiteForm(BaseModel):
    name: str = ""
    action: str = ""
    method: str = ""
    inputs: list[WebsiteInput] = Field(default_factory=list)


class WebsiteMap(BaseModel):
    url: str
    title: str = ""
    description: str = ""
    navigation: list[WebsiteLink] = Field(default_factory=list)
    links: list[WebsiteLink] = Field(default_factory=list)
    buttons: list[WebsiteButton] = Field(default_factory=list)
    headings: list[WebsiteHeading] = Field(default_factory=list)
    inputs: list[WebsiteInput] = Field(default_factory=list)
    forms: list[WebsiteForm] = Field(default_factory=list)
    authentication_required: bool = False
    captcha_present: bool = False
    human_intervention_required: bool = False
    console_errors: list[str] = Field(default_factory=list)
    console_warnings: list[str] = Field(default_factory=list)