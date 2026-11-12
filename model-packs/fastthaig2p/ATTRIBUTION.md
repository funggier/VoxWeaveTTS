# FastThaiG2P Kokoro Thai Som — provenance and third-party licenses

**Upstream:** FastThaiG2P, developed by Charin Polpanumas / Amazon Web Services  
**Repository:** https://github.com/awslabs/FastThaiG2P  
**Original model assets:** https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0  
**VoxWeaveTTS package:** `fastthaig2p-thai-som` v0.3.0.

## Components and licenses

| Component | License / evidence | Conditions / uncertainty |
|---|---|---|
| FastThaiG2P software / release assets | Apache License 2.0 in the upstream repository, with NOTICE | Preserve Apache-2.0 license, copyright notice and attribution when redistributing the model assets; upstream README provides the release assets |
| Kokoro-82M starting checkpoint | Original Kokoro model is published under Apache-2.0 | Thai model was fine-tuned from Kokoro, so original model credit is retained |
| Som TTS training dataset | **CC BY 4.0** as declared by the dataset publisher, Wannaphong Phatthiyaphaibun | Give creator, dataset name, link and license; indicate that the distributed model is a trained artifact, not the original dataset |
| `kokoro_thai.onnx` | Derived Thai-finetuned ONNX model published with FastThaiG2P v0.3.0 | Attribution included; a full independent rights audit of every training artifact has not been completed |
| `thai_som.npy` voicepack | Released alongside the model | Do not claim exclusive voice rights, consent or warranty absent upstream evidence |

## Required attribution

**FastThaiG2P** — Charin Polpanumas and Amazon Web Services.  
Project: https://github.com/awslabs/FastThaiG2P  
License: Apache-2.0 (included as `LICENSE.txt`).  
Upstream NOTICE: included unchanged as `NOTICE.txt`.

**Som TTS dataset** — Wannaphong Phatthiyaphaibun, *Som TTS dataset: Open Data Thai TTS*, version 1.0.0 (2026), DOI https://doi.org/10.5281/zenodo.21530909  
Source: https://huggingface.co/datasets/pythainlp/som_tts_dataset  
License: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/  
The model package does **not** contain the original Som TTS dataset. The weights were fine-tuned using that dataset according to the FastThaiG2P paper/repository.

**Kokoro** — Original Kokoro-82M weights, originally Apache-2.0.  
https://huggingface.co/hexgrad/Kokoro-82M

## Conditions and disclaimer

Redistribution is based on the **upstream published Apache-2.0 license/NOTICE and attribution** for the released FastThaiG2P artifacts, plus the CC BY 4.0 attribution for Som TTS. Repackaging is a file-layout conversion for VoxWeaveTTS; it does not change model weights or license.

Preserve these notices, upstream links and other third-party licenses. The source licenses may permit commercial use, but **VoxWeaveTTS has not audited every training/voice right and makes no commercial-use warranty**. Users are responsible for assessing their own use and for fulfilling all applicable upstream conditions. This disclaimer grants no rights beyond the actual licenses.

References: https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0 ; https://huggingface.co/datasets/pythainlp/som_tts_dataset ; https://arxiv.org/abs/2608.12814
