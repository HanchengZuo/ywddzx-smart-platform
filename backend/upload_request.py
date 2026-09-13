"""Keep upload limits everywhere except the authenticated full-backup importer."""
from flask import Request


class PlatformRequest(Request):
    @property
    def max_content_length(self):
        if self.method == 'POST' and self.endpoint == 'import_management_full_backup':
            return None
        return super().max_content_length

    @max_content_length.setter
    def max_content_length(self, value):
        Request.max_content_length.fset(self, value)
