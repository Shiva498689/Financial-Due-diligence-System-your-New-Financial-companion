# import modal

# app = modal.App("qwen-inference-service")

# image = (
#     modal.Image.from_registry(
#         "nvidia/cuda:12.1.1-devel-ubuntu22.04", 
#         add_python="3.11"
#     )
#     .pip_install("fastapi[standard]", "pydantic", "vllm")
#     .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
# )

# @app.cls(
#     gpu="A10G",   
#     max_containers=1 ,           
#     image=image, 
#     scaledown_window=15, # CREDIT PROTECTION: Drops from 300 to 15s to save idle credit drain
#     timeout=600
# )
# class QwenModel:
#     @modal.enter()
#     def startup(self):
#         from vllm import LLM
#         # Load the Qwen model with safety constraints
#         self.llm = LLM(
#             model="Qwen/Qwen2.5-7B-Instruct", 
#             max_model_len=8192,
#             trust_remote_code=True,
#             enforce_eager=True # BACKEND PROTECTION: Forces instant fallback stability if JIT compilers hitch
#         )

#     @modal.method()
#     def generate(self, prompt: str, system_directive: str = None, temperature: float = 0.0) -> str:
#         from vllm import SamplingParams
        
#         if system_directive:
#             full_prompt = f"<|im_start|>system\n{system_directive}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
#         else:
#             full_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
            
#         sampling_params = SamplingParams(
#             temperature=temperature,
#             max_tokens=2048,
#             stop=["<|im_end|>", "<|endoftext|>"]
#         )
        
#         outputs = self.llm.generate([full_prompt], sampling_params)
#         return outputs[0].outputs[0].text


# @app.function(image=image)
# @modal.asgi_app()
# def web_app():
#     from fastapi import FastAPI, Request
#     from fastapi.responses import JSONResponse
    
#     web_api = FastAPI(title="Qwen Inference Pipeline")
    
#     @web_api.post("/")
#     async def run_inference(request: Request):
#         data = await request.json()
        
#         # 1. Parse the OpenAI-style 'messages' payload coming from your local script
#         messages = data.get("messages", [])
#         prompt = ""
#         system_directive = None
        
#         for msg in messages:
#             if msg.get("role") == "system":
#                 system_directive = msg.get("content")
#             elif msg.get("role") == "user":
#                 prompt = msg.get("content")
                
#         temperature = data.get("temperature", 0.0)
        
#         # 2. Instantiate the remote container class
#         model_runner = QwenModel()
#         response_text = model_runner.generate.remote(
#             prompt=prompt, 
#             system_directive=system_directive, 
#             temperature=temperature
#         )
        
#         # 3. Return the exact JSON structure your local script expects
#         return JSONResponse(content={
#             "choices": [
#                 {
#                     "message": {
#                         "content": response_text
#                     }
#                 }
#             ]
#         })
        
#     return web_api
import os
import modal

# Define the Modal App
app = modal.App("qwen-7b-summarizer")

# Create a persistent volume to cache Hugging Face model weights
hf_volume = modal.Volume.from_name("hf-hub-cache", create_if_missing=True)

# Define the container image with corrected dependencies
# image = (
#     modal.Image.debian_slim(python_version="3.10")
#     .pip_install(
#         "vllm>=0.6.4",  # Fixed the Qwen 2.5 config parsing bug
#         "transformers",
#         "fastapi",
#         "pydantic"
#     )
# )
image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.10")
    .apt_install("git", "build-essential")
    .pip_install(
        "ninja",        # Required build system for FlashInfer JIT compilation
        "vllm>=0.6.4",
        "transformers",
        "fastapi",
        "pydantic"
    )
)

MODEL_DIR = "/cache"
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

@app.cls(
    gpu="A10G", 
    image=image,
    volumes={MODEL_DIR: hf_volume},
    timeout=1200
)
class QwenModel:
    @modal.enter()
    def load_model(self):
        """Initializes the vLLM engine inside the container safely."""
        from vllm import LLMEngine, EngineArgs
        from transformers import AutoTokenizer

        print("Loading Qwen 7B Instruct model into GPU memory...")
        
        # Configure vLLM engine arguments
        engine_args = EngineArgs(
            model=MODEL_NAME,
            download_dir=MODEL_DIR,
            max_model_len=4096,
            gpu_memory_utilization=0.90,
            enforce_eager=True  # Provides stability across cloud container scales
        )
        
        self.engine = LLMEngine.from_engine_args(engine_args)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=MODEL_DIR)
        print("Model loaded successfully.")

    @modal.fastapi_endpoint(method="POST")
    def summarize(self, data: dict):
        """
        REST API endpoint to process a text chunk and return a 75% compressed bullet point summary.
        """
        from vllm import SamplingParams
        import uuid

        text_chunk = data.get("text", "")
        if not text_chunk:
            return {"error": "No text provided"}, 400

        # Formulate a structured prompt optimized for financial extraction
        system_prompt = (
            "You are an expert financial due diligence analyst. Your job is to extract the absolute essence "
            "of the following text into exactly 3 to 4 dense, highly informative bullet points. "
            "Reduce the total word count by approximately 75% while retaining critical quantitative values, "
            "risks, operational details, names, and regulatory issues. Do not include any introductory or concluding text."
        )
        
        full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{text_chunk}<|im_end|>\n<|im_start|>assistant\n"

        sampling_params = SamplingParams(
            temperature=0.1,  # Keep it deterministic and factual
            max_tokens=512,
            top_p=0.95
        )

        # Generate unique request id for vLLM scheduler
        request_id = str(uuid.uuid4())
        self.engine.add_request(request_id, full_prompt, sampling_params)

        # Poll the engine for execution outputs
        final_output = None
        while self.engine.has_unfinished_requests():
            request_outputs = self.engine.step()
            for output in request_outputs:
                if output.request_id == request_id:
                    final_output = output

        if final_output:
            generated_text = final_output.outputs[0].text.strip()
            return {"summary": generated_text}
        
        return {"error": "Generation failed"}, 500