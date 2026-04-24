from __future__ import annotations

import subprocess
import urllib.parse
import webbrowser
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ManualSearchInput(BaseModel):
    query: str = Field(..., description="Search keywords to open in browser")
    ref_number: int = Field(..., description="The reference number that needs manual search")
    reason: str = Field(default="", description="Why automated search failed")


class ManualSearchTool(BaseTool):
    name: str = "manual_search"
    description: str = (
        "Use ONLY after automated scholar_search has failed multiple times. "
        "Sends a desktop notification and opens a search page in the browser "
        "so the user can manually find the correct paper."
    )
    args_schema: Type[BaseModel] = ManualSearchInput

    def _run(self, query: str, ref_number: int, reason: str = "") -> str:
        try:
            subprocess.run(
                [
                    "powershell", "-ExecutionPolicy", "Bypass", "-Command",
                    "Import-Module BurntToast; New-BurntToastNotification "
                    f"-Text 'Citation Review','Ref [{ref_number}]: Need manual search'",
                ],
                timeout=10,
                capture_output=True,
            )
        except Exception:
            pass

        search_url = (
            "https://scholar.google.com/scholar?q="
            + urllib.parse.quote(query)
        )
        try:
            webbrowser.open(search_url)
        except Exception:
            pass

        return (
            f"MANUAL SEARCH NEEDED for reference [{ref_number}].\n"
            f"Reason: {reason}\n"
            f"Search opened in browser with query: {query}\n"
            f"URL: {search_url}\n\n"
            f"Please ask the user to provide the correct paper's DOI or full title. "
            f"If the user provides a DOI starting with '10.', you can use "
            f"scholar_search with api='crossref' to fetch its full metadata."
        )
