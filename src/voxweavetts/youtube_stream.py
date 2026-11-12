"""YouTube liveChatMessages.streamList: read-only, cancellation-safe gRPC client.

Google's official Streaming Live Chat guide specifies a gRPC server-streaming
method (NOT an HTTP JSON/SSE URL). This small, partial protobuf descriptor
contains only the fields needed to read text messages and authors. The field
numbers, service name and request metadata follow the public Google proto:
https://developers.google.com/youtube/v3/live/streaming-live-chat

grpcio and google.protobuf are optional at import time. The Portable build
must include both for streaming. No keys in URLs, log strings or exceptions.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any


class StreamUnavailable(Exception):
    """The optional stream transport is not installed or not implemented."""


@lru_cache(maxsize=1)
def _wire_types():
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    from google.protobuf.descriptor_pb2 import FieldDescriptorProto as F

    descriptor = descriptor_pb2.FileDescriptorProto()
    descriptor.name = "voxweavetts/youtube_stream_subset.proto"
    descriptor.package = "youtube.api.v3"
    descriptor.syntax = "proto2"

    def make_message(name: str, fields: list[tuple]):
        message = descriptor.message_type.add()
        message.name = name
        for field_name, number, kind, repeated, message_type in fields:
            field = message.field.add()
            field.name, field.number, field.type = field_name, number, kind
            field.label = F.LABEL_REPEATED if repeated else F.LABEL_OPTIONAL
            if message_type:
                field.type_name = f".youtube.api.v3.{message_type}"

    string = F.TYPE_STRING
    msg = F.TYPE_MESSAGE
    integer = F.TYPE_INT32
    make_message("LiveChatMessageListRequest", [
        ("live_chat_id", 1, string, False, None),
        ("page_token", 99, string, False, None),
        ("part", 100, string, True, None),
    ])
    make_message("LiveChatTextMessageDetails", [
        ("message_text", 1, string, False, None),
    ])
    make_message("LiveChatMessageAuthorDetails", [
        ("display_name", 103, string, False, None),
    ])
    make_message("LiveChatMessageSnippet", [
        ("type", 1, integer, False, None),
        ("text_message_details", 19, msg, False, "LiveChatTextMessageDetails"),
    ])
    make_message("LiveChatMessage", [
        ("id", 101, string, False, None),
        ("snippet", 2, msg, False, "LiveChatMessageSnippet"),
        ("author_details", 3, msg, False, "LiveChatMessageAuthorDetails"),
    ])
    make_message("LiveChatMessageListResponse", [
        ("offline_at", 2, string, False, None),
        ("next_page_token", 100602, string, False, None),
        ("items", 1007, msg, True, "LiveChatMessage"),
    ])
    pool = descriptor_pool.DescriptorPool()
    pool.Add(descriptor)
    package = "youtube.api.v3."
    return tuple(message_factory.GetMessageClass(
        pool.FindMessageTypeByName(package + name))
        for name in ("LiveChatMessageListRequest", "LiveChatMessageListResponse"))


class StreamConnection:
    """One gRPC server-stream call; close() cancels the blocked iterator."""

    def __init__(self, chat_id: str, api_key: str,
                 page_token: str | None = None) -> None:
        try:
            import grpc
            request_type, response_type = _wire_types()
        except ImportError as exc:
            raise StreamUnavailable("YouTube stream transport requires grpcio and protobuf") from exc
        self._channel: Any = grpc.secure_channel("youtube.googleapis.com:443",
                                                grpc.ssl_channel_credentials())
        self._closed = False
        try:
            request = request_type(live_chat_id=chat_id,
                                   part=["snippet", "authorDetails"])
            if page_token:
                request.page_token = page_token
            rpc = self._channel.unary_stream(
                "/youtube.api.v3.V3DataLiveChatMessageService/StreamList",
                request_serializer=lambda item: item.SerializeToString(),
                response_deserializer=response_type.FromString,
            )
            self._call = rpc(request, metadata=(("x-goog-api-key", api_key),),
                             timeout=1800)
        except Exception:
            self._channel.close()
            raise

    def __iter__(self):
        return self

    def __next__(self) -> dict[str, Any]:
        result = next(self._call)
        return {
            "nextPageToken": result.next_page_token,
            "offlineAt": result.offline_at,
            "items": [
                {
                    "id": row.id,
                    "snippet": {
                        "type": "textMessageEvent" if row.snippet.type == 1
                                else "other",
                        "textMessageDetails": {
                            "messageText": row.snippet.text_message_details.message_text,
                        },
                    },
                    "authorDetails": {
                        "displayName": row.author_details.display_name,
                    },
                }
                for row in result.items
            ],
        }

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._call.cancel()
            self._channel.close()


def grpc_available() -> bool:
    """No import side effects: CI may run its stdlib-only test matrix."""
    try:
        import grpc  # noqa: F401
        from google.protobuf import descriptor_pb2  # noqa: F401
        return True
    except ImportError:
        return False
