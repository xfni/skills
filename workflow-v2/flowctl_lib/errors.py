class FlowctlError(Exception):
    def __init__(self, code, message=None, **details):
        self.code = code
        self.message = message or code
        self.details = details
        super().__init__(f"{code}: {self.message}")

    def as_dict(self):
        result = {"ok": False, "code": self.code, "message": self.message}
        if self.details:
            result["details"] = self.details
        return result
