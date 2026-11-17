"""Exact upstream Wayu Paxa Edge original NC binary pins for native v2.

This is *trusted first-party code*, not a manifest-supplied whitelist.
Serialized PyTorch .pth/.pt files are admitted only for this exact pinned
upstream package, and verified again before isolated-worker deserialization.
"""
from __future__ import annotations

SOURCE_URL = "https://huggingface.co/wayu-ai/wayu-paxa-tts-edge"
LICENSE_SPDX = "CC-BY-NC-4.0"
PACKAGE_ID = "wayu-paxa-edge-nc"
PACKAGE_VERSION = "1.0.0"

PINNED_ASSETS = {
    "config.json": "82bdfb49f558c262a2eeebc40c78758e48a90ef2d56ac8bd0678aac9d33a089e",
    "model.pth": "eb26ac6f7da4c651389b28793d0ab59be8fa7e3e7cc5d350278b2a8d0a4d7370",
    "voices/f_elderly_low.pt": "52bb2fe51db2f16b2ec45cccdd94c60207a307291aeefa43daf9d7da64534fd6",
    "voices/f_elderly_soft.pt": "8a9d0c9fa39548458d28f36395e8b6688171fcf52705cad84b6a4e2261d9ec62",
    "voices/f_mid_clear.pt": "60c27208ac13d62027833bad1e9e27728b60b3312b56deffb21b135d248e560a",
    "voices/f_mid_warm.pt": "70e581e609475023c208de252a1261be5b521ba710f67e2c81a9c12572555f37",
    "voices/f_teen_bright.pt": "8deb6ea18d3a031d3c9e0ee95cd6c821b17b176dab066eed8cd1edec0fe94210",
    "voices/f_young_bright.pt": "4a31d0aebe0f933b44338cb4ee7c3d1d02712734c01fa9adf1bc63b8f8504e22",
    "voices/f_young_clear.pt": "ac1b78525ed2e3ebd21ddc19736307b5ad30f4036bfd46e679b2b80ab1364f56",
    "voices/f_young_warm.pt": "62ae8e533e82d6bd51965af58be171d95298c135a389a08d77af467632080253",
    "voices/m_elderly_deep.pt": "0852a4b10a02422c70dcdee702a698cf48ee0135c84b0bdfce609d4a2d31485d",
    "voices/m_mid_warm.pt": "61fef6ffa19cee7c6d539fb2039bd5bac57647cb649e630f82f2b0d167d096b4",
    "voices/m_teen_bright.pt": "8a57087e0e1de3cb2d96cc2020a730301cc06c244449518b7975c0b89674153d",
    "voices/m_young_clear.pt": "86154fe8cf060516dde67fe9ce81fd11ef3e550b3bab66db0fd42ea46cae3623",
}
SOURCE_REVISION = "8196688df56a8d08ccfa186505343adff412ab6b"

