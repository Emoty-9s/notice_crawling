"""Read-only local ONNX embeddings. Never imports a hub/download/API client."""
import hashlib
import json
import os
import sys
from pathlib import Path


class ModelError(ValueError):
    pass


def model_directory():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)/'models/performance_classifier'
    return Path(__file__).resolve().parents[2]/'resources/models/performance_classifier'


class LocalEncoder:
    active_sessions = 0

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else model_directory()
        self.session = self.tokenizer = None
        self._counted = False
        try:
            self.manifest = json.loads((self.directory/'manifest.json').read_text(encoding='utf-8'))
            if self.manifest['license'] != 'mit':
                raise ModelError('INVALID_MODEL_LICENSE')
            for name in ('model.onnx', 'tokenizer.json'):
                path = self.directory/name
                artifact = self.manifest['artifacts'][name]
                if path.stat().st_size != artifact['bytes']:
                    raise ModelError('MODEL_SIZE_MISMATCH')
                with path.open('rb') as source:
                    digest = hashlib.file_digest(source, 'sha256').hexdigest()
                if digest != artifact['sha256']:
                    raise ModelError('MODEL_HASH_MISMATCH')
            import numpy as np
            import onnxruntime as ort
            ort.disable_telemetry_events()
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            from tokenizers import Tokenizer
            self.np = np
            options = ort.SessionOptions()
            options.intra_op_num_threads = min(2, os.cpu_count() or 1)
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.enable_cpu_mem_arena = False
            options.log_severity_level = 3
            self.session = ort.InferenceSession(str(self.directory/'model.onnx'), sess_options=options,
                                                providers=['CPUExecutionProvider'])
            self.session.disable_fallback()
            self.tokenizer = Tokenizer.from_file(str(self.directory/'tokenizer.json'))
            self.tokenizer.enable_truncation(max_length=192)
            self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
            self.version = self.manifest['model_version']
            self._counted = True
            LocalEncoder.active_sessions += 1
        except Exception:
            self.close()
            raise ModelError('LOCAL_MODEL_UNAVAILABLE') from None

    def encode(self, texts, *, batch_size=16, cancel=None):
        np = self.np
        vectors = []
        try:
            names = {v.name for v in self.session.get_inputs()}
            for start in range(0, len(texts), batch_size):
                if cancel and cancel.is_set():
                    raise ModelError('CANCELLED')
                batch = self.tokenizer.encode_batch(['query: ' + text for text in texts[start:start+batch_size]])
                ids = np.array([item.ids for item in batch], dtype=np.int64)
                mask = np.array([item.attention_mask for item in batch], dtype=np.int64)
                inputs = {'input_ids': ids, 'attention_mask': mask}
                if 'token_type_ids' in names:
                    inputs['token_type_ids'] = np.zeros_like(ids)
                output = self.session.run(None, inputs)[0]
                if output.ndim == 3:
                    output = (output * mask[..., None]).sum(axis=1)/np.maximum(mask.sum(axis=1)[:, None], 1)
                vectors.append(output/np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-9))
            return np.concatenate(vectors, axis=0) if vectors else np.empty((0, 384), dtype=np.float32)
        except ModelError:
            raise
        except Exception:
            raise ModelError('LOCAL_INFERENCE_FAILED') from None

    def close(self):
        self.session = self.tokenizer = None
        if self._counted:
            LocalEncoder.active_sessions -= 1
            self._counted = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
