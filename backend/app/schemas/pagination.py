# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Shared limit/offset pagination params for list endpoints. The response
# stays a plain list (no breaking change to existing clients) — total count
# goes in the X-Total-Count header instead, set by each route after calling
# its service's paginated list function.

from fastapi import Query


class PageParams:
    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Max items to return"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset
