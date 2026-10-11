# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Weaviate connection, built from Settings.WEAVIATE_URL (+ the separate gRPC
# port the v4 client needs). Cached so the connection is opened once per
# process, not once per request.

import warnings
from functools import lru_cache
from urllib.parse import urlparse

# weaviate.classes.init.Auth pulls in authlib's (unused) OIDC assertion
# client, which falls back from the optional "httpx2" package to plain
# httpx and warns every time. Importing authlib.deprecate first lets us
# register our "ignore" filter after authlib's own `simplefilter("always",
# ...)` call for this warning class, so ours takes precedence.
from authlib.deprecate import AuthlibDeprecationWarning

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)

import weaviate  # noqa: E402
from weaviate.classes.init import Auth  # noqa: E402
from weaviate.client import WeaviateClient  # noqa: E402

from app.core.config import settings  # noqa: E402


@lru_cache
def get_weaviate_client() -> WeaviateClient:
    raw_url = settings.WEAVIATE_URL
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"
    parsed = urlparse(raw_url)
    is_secure = parsed.scheme == "https"
    auth_credentials = (
        Auth.api_key(settings.WEAVIATE_API_KEY) if settings.WEAVIATE_API_KEY else None
    )

    http_host = parsed.hostname or "localhost"
    # Weaviate Cloud serves gRPC on a "grpc-" subdomain of the REST host, both
    # over 443; local/self-hosted instances serve both on the same host with
    # a distinct gRPC port (WEAVIATE_GRPC_PORT, default 50051).
    grpc_host = f"grpc-{http_host}" if is_secure else http_host
    grpc_port = 443 if is_secure else settings.WEAVIATE_GRPC_PORT

    return weaviate.connect_to_custom(
        http_host=http_host,
        http_port=parsed.port or (443 if is_secure else 8080),
        http_secure=is_secure,
        grpc_host=grpc_host,
        grpc_port=grpc_port,
        grpc_secure=is_secure,
        auth_credentials=auth_credentials,
    )
