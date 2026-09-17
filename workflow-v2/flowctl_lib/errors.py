class FlowctlError(Exception):
    def __init__(self, code, message=None, **details):
        self.code = code
        self.message = message or code
        self.details = details
        super().__init__(f"{code}: {self.message}")

    def as_dict(self):
        result = {"ok": False, "code": self.code, "message": self.message}
        result['details'] = {
            'suggested_actions': ['Reload status before retrying; inspect current facts and the owning stage. Do not invent PASS, erase history or clear actual pauses.'],
            **self.details,
        }
        return result
