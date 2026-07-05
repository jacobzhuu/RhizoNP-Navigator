from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    text: str
    url: str

    def json(self) -> Any:
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code} for {self.url}")


class HttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        ...

    def post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        ...


class UrllibHttpClient:
    _USER_AGENT = "RhizoNP-Navigator/0.1"

    def _request(
        self,
        url: str,
        *,
        method: str,
        params: dict[str, str] | None,
        timeout: float,
    ) -> HttpResponse:
        request_url = url
        if params:
            query = urllib.parse.urlencode(params)
            separator = "&" if "?" in url else "?"
            request_url = f"{url}{separator}{query}"
        request = urllib.request.Request(
            request_url,
            method=method,
            headers={"User-Agent": self._USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return HttpResponse(
                    status_code=response.status,
                    text=body,
                    url=request_url,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(status_code=exc.code, text=body, url=request_url)
        except TimeoutError as exc:
            raise TimeoutError(f"Request timed out after {timeout}s: {request_url}") from exc

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        return self._request(url, method="GET", params=params, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        return self._request(url, method="POST", params=params, timeout=timeout)
