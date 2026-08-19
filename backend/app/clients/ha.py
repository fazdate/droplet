"""Home Assistant REST API client — used only to push actionable notifications
(plan section 2.4/4.8). All other HA interaction (automations forwarding button
presses) lives on the HA side and calls back into our /api/ha/action webhook.
"""

import httpx


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _call_notify(self, target: str, payload: dict) -> None:
        url = f"{self._base_url}/api/services/notify/{target}"
        response = httpx.post(url, json=payload, headers=self._headers(), timeout=self._timeout)
        response.raise_for_status()

    def notify(
        self,
        *,
        targets: list[str],
        title: str,
        message: str,
        tag: str,
        actions: list[dict],
        click_action: str,
    ) -> None:
        payload = {
            "title": title,
            "message": message,
            "data": {"tag": tag, "actions": actions, "clickAction": click_action},
        }
        for target in targets:
            self._call_notify(target, payload)

    def clear_notification(self, *, targets: list[str], tag: str) -> None:
        payload = {"message": "clear_notification", "data": {"tag": tag}}
        for target in targets:
            self._call_notify(target, payload)
