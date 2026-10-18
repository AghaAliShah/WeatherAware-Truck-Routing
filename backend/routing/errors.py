import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class UpstreamError(Exception):
    """A third-party service (routing / geocoding / weather) failed."""


class PlanningError(Exception):
    """The request is well-formed but cannot be planned (e.g. no road route)."""


def exception_handler(exc, context):
    if isinstance(exc, UpstreamError):
        logger.warning("Upstream failure: %s", exc)
        return Response({"error": str(exc)}, status=502)
    if isinstance(exc, PlanningError):
        return Response({"error": str(exc)}, status=422)
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error", exc_info=exc)
        return Response({"error": "Internal server error"}, status=500)
    return response
