# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_onnx.ipynb (unless otherwise specified).

__all__ = ['fastONNX']

# Cell
from .soft_dependencies import SoftDependencies
if not SoftDependencies.check()['onnxcpu']:
    raise ImportError("The onnxcpu or onnxgpu module is not installed.")

# Cell
from fastai2.learner import Learner
from fastcore.all import *
import torch
from torch import tensor, Tensor

import onnxruntime as ort

# Cell
#export
from .inference.inference import _decode_loss

# Cell
#export
class fastONNX():
    "ONNX wrapper for `Learner`"
    def __init__(self, fn):
        self.ort_session = ort.InferenceSession(fn+'.onnx')
        try:
            self.ort_session.set_providers(['CUDAExecutionProvider'])
            cpu = False
        except:
            self.ort_session.set_providers(['CPUExecutionProvider'])
            cpu = True
        self.dls = torch.load(fn+'.pkl')

    def to_numpy(self, t:tensor): return t.detach.cpu().numpy() if t.requires_grad else t.cpu().numpy()

    def predict(self, inps):
        "Predict a single numpy item"
        if isinstance(inps[0], Tensor): inps = [self.to_numpy(x) for x in inps]
        names = [i.name for i in self.ort_session.get_inputs()]
        xs = {name:x for name,x in zip(names,inps)}
        outs = self.ort_session.run(None, xs)
        return outs

    def get_preds(self, dl=None, raw_outs=False, decoded_loss=True, fully_decoded=False):
        "Get predictions with possible decoding"
        inps, outs, dec_out, raw = [], [], [], []
        loss_func = self.dls.loss_func
        is_multi, n_inp = False, self.dls.n_inp
        if n_inp > 1:
            is_multi = true
            [inps.append([]) for _ in range(n_inp)]
        for batch in dl:
            batch_np = []
            if is_multi:
                for i in range(n_inp):
                    item = self.to_numpy(batch[i])
                    inps[i].append(item)
                    batch_np.append(item)
            else:
                inps.append(self.to_numpy(batch[:n_inp]))
            if decoded_loss or fully_decoded:
                out = self.predict(batch_np)
                raw.append(out)
                dec_out.append(loss_func.decodes(tensor(out)))
            else:
                raw.append(self.predict(batch_np))
        axis = 1 if len(dl) > 1 else 0
        raw = np.concatenate(raw, axis=axis)
        if decoded_loss or fully_decoded:
            dec_out = np.concatenate(dec_out, axis=axis)
        if not raw_outs:
            try: outs.insert(0, loss_func.activation(tensor(raw)).numpy())
            except: outs.insert(0, dec_out)
        else:
            outs.insert(0, raw)
        if decoded_loss: outs = _decode_loss(self.dls.vocab, dec_out, outs)
        return outs

    def test_dl(self, test_items, **kwargs): return self.dls.test_dl(test_items, **kwargs)