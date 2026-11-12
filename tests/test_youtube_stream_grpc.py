"""Real local gRPC transport roundtrip; NEVER contacts Google's API."""
from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

try:
    import grpc
    import google.protobuf  # noqa: F401
except ImportError:
    grpc = None

from voxweavetts.youtube_stream import StreamConnection, _wire_types


@unittest.skipUnless(grpc is not None, "grpcio/protobuf not installed in stdlib-only CI")
class LocalGrpcStreamTests(unittest.TestCase):
    def test_official_wire_shape_metadata_cancellation_and_thai_message(self):
        request_type, response_type = _wire_types()
        observed = []

        def handle(request, context):
            metadata = dict(context.invocation_metadata())
            observed.append({
                "chat": request.live_chat_id,
                "parts": tuple(request.part),
                "cursor": request.page_token,
                "key": metadata.get("x-goog-api-key"),
            })
            response = response_type(next_page_token="cursor-next")
            item = response.items.add()
            item.id = "synthetic-youtube-msg"
            item.snippet.type = 1
            item.snippet.text_message_details.message_text = "สวัสดีผู้ชมทุกท่าน"
            item.author_details.display_name = "คนไทย"
            yield response

        server = grpc.server(ThreadPoolExecutor(max_workers=2))
        method = grpc.unary_stream_rpc_method_handler(
            handle,
            request_deserializer=request_type.FromString,
            response_serializer=lambda response: response.SerializeToString(),
        )
        service = grpc.method_handlers_generic_handler(
            "youtube.api.v3.V3DataLiveChatMessageService",
            {"StreamList": method},
        )
        server.add_generic_rpc_handlers((service,))
        port = server.add_insecure_port("127.0.0.1:0")
        self.assertGreater(port, 0)
        server.start()
        real_secure_channel = grpc.secure_channel
        try:
            with patch.object(grpc, "secure_channel",
                              side_effect=lambda _target, _cred: grpc.insecure_channel(
                                  f"127.0.0.1:{port}")):
                connection = StreamConnection(
                    "Cg0K_dummy_chat", "TEST_KEY_NEVER_SENT_TO_GOOGLE", "resume-123")
                try:
                    packet = next(connection)
                    self.assertEqual(packet["nextPageToken"], "cursor-next")
                    self.assertEqual(packet["items"][0]["id"], "synthetic-youtube-msg")
                    self.assertEqual(packet["items"][0]["snippet"][
                        "textMessageDetails"]["messageText"], "สวัสดีผู้ชมทุกท่าน")
                    self.assertEqual(packet["items"][0]["authorDetails"]["displayName"],
                                     "คนไทย")
                    self.assertEqual(observed, [{
                        "chat": "Cg0K_dummy_chat",
                        "parts": ("snippet", "authorDetails"),
                        "cursor": "resume-123",
                        "key": "TEST_KEY_NEVER_SENT_TO_GOOGLE",
                    }])
                finally:
                    connection.close()
        finally:
            server.stop(grace=0).wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
