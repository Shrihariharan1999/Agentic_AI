from app.models.factory import model_factory
from app.schemas.discovery import DiscoveryResult


DISCOVERY_EXTRACTION_PROMPT = """
You are the Website Discovery Extraction Agent.

Convert the browser discovery evidence into the provided structured schema.

Extract only information supported by the browser evidence.

Identify:

- Website URL
- Website title
- Website description when available
- Navigation links
- Important links
- Buttons
- Headings
- Input fields
- Forms
- Authentication requirements
- CAPTCHA presence
- Human intervention requirements
- Console errors
- Console warnings

Rules:

- Do not invent information.
- Do not infer that CAPTCHA exists unless the evidence supports it.
- Do not infer authentication is required unless the evidence supports it.
- Preserve URLs exactly when available.
- Prefer visible text from the browser evidence.
- Ignore advertisements unless they are relevant to interaction.
- Avoid duplicating identical links.
"""


class DiscoveryExtractor:
    def __init__(self):
        self.model = model_factory.get("discovery_structurer")

    def extract(self, browser_evidence: str) -> DiscoveryResult:
        prompt = f"""
{DISCOVERY_EXTRACTION_PROMPT}

BROWSER DISCOVERY EVIDENCE:

{browser_evidence}
"""

        try:
            response = self.model.with_structured_output(DiscoveryResult).invoke(prompt)
            if response and hasattr(response, "website"):
                return response
        except Exception as e:
            print(f"[DiscoveryExtractor Warning] Structured parsing failed: {e}. Building fallback DiscoveryResult.")

        # Resilient fallback: parse JSON or extract from evidence text
        import json
        import re
        from app.schemas.website import WebsiteMap, InteractiveElement, NavigationLink, FormStructure

        site_title = "Target Website"
        target_url = "https://example.com"
        links = []
        buttons = []
        inputs = []
        forms = []

        try:
            # Check if evidence contains JSON
            json_match = re.search(r'\{.*\}', browser_evidence, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                site_title = parsed.get("title", site_title)
                for l in parsed.get("links", []):
                    links.append(NavigationLink(href=l.get("href", ""), text=l.get("text", "Link")))
                for b in parsed.get("buttons", []):
                    buttons.append(InteractiveElement(selector=b.get("selector", "button"), text=b.get("text", "Button"), element_type="button"))
                for i in parsed.get("inputs", []):
                    inputs.append(InteractiveElement(selector=i.get("selector", "input"), text=i.get("name", "input"), element_type=i.get("type", "text")))
                for f in parsed.get("forms", []):
                    forms.append(FormStructure(id="form-1", action=f.get("action", "")))
        except Exception:
            pass

        if not links:
            # Simple regex search for URLs in evidence
            url_matches = re.findall(r'https?://[^\s<>"\']+', browser_evidence)
            if url_matches:
                target_url = url_matches[0]
                for u in url_matches[1:15]:
                    links.append(NavigationLink(href=u, text="Page Link"))

        return DiscoveryResult(
            website=WebsiteMap(
                url=target_url,
                title=site_title,
                description=f"Discovered webpage {site_title}",
                links=links,
                navigation=links[:5],
                buttons=buttons,
                inputs=inputs,
                forms=forms,
                authentication_required=False,
                captcha_present=False
            )
        )