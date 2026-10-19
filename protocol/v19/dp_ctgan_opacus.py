"""DP-CTGAN on current opacus, written for V19 (design: ../../29_FROZEN_DESIGN_V19.md). Our own code, about 60 lines, on top of the
standard CTGAN (ctgan 0.12.1: its DataTransformer, DataSampler, Generator and Discriminator classes, unchanged) and opacus 1.5.2.
Discriminator: pac = 1 and binary cross-entropy, because the CTGAN gradient penalty needs a double backward pass that per-sample clipping does
not support. Each discriminator step sees B real rows and B generated rows; every row's gradient is clipped to norm 1 and Gaussian noise with
standard deviation sigma x 1 is added by opacus' DPOptimizer. Accounting: opacus' RDP accountant, one step per discriminator update with sample
rate B / n, delta = 1/(n sqrt n). Training stops before the step that would take the spent epsilon over the target, so the spent value never
exceeds the target. Generator: trained only through the discriminator, which is post-processing.
Known limits, stated in the design: rows are drawn by CTGAN's conditional sampler, not by Poisson sampling, so the accounting is approximate;
the conditioning vectors use the exact category frequencies of the training data, outside the budget, as in smartnoise."""
import numpy as np, torch, pandas as pd
from torch import optim, nn
from ctgan import CTGAN
from ctgan.synthesizers.ctgan import Discriminator, Generator
from ctgan.data_transformer import DataTransformer
from ctgan.data_sampler import DataSampler
from opacus import GradSampleModule
from opacus.optimizers import DPOptimizer
from opacus.accountants import RDPAccountant

class DPCTGANModern(CTGAN):
    def __init__(self, epsilon=1.0, delta=None, sigma=1.0, clip=1.0, max_epochs=300, batch_size=64, **kw):
        super().__init__(batch_size=batch_size, pac=1, epochs=max_epochs, enable_gpu=False, **kw)
        self.eps_target=epsilon; self.delta=delta; self.sigma=sigma; self.clip=clip; self.max_epochs=max_epochs

    def fit(self, train_data, discrete_columns=()):
        self._transformer=DataTransformer(); self._transformer.fit(train_data, discrete_columns)
        X=self._transformer.transform(train_data); n=len(X)
        self._data_sampler=DataSampler(X,self._transformer.output_info_list,self._log_frequency)
        ddim=self._transformer.output_dimensions; cdim=self._data_sampler.dim_cond_vec(); B=self._batch_size
        self._generator=Generator(self._embedding_dim+cdim,self._generator_dim,ddim)
        D=GradSampleModule(Discriminator(ddim+cdim,self._discriminator_dim,pac=1))
        oG=optim.Adam(self._generator.parameters(),lr=self._generator_lr,betas=(0.5,0.9),weight_decay=self._generator_decay)
        oD=DPOptimizer(optim.Adam(D.parameters(),lr=self._discriminator_lr,betas=(0.5,0.9),weight_decay=self._discriminator_decay),
                       noise_multiplier=self.sigma,max_grad_norm=self.clip,expected_batch_size=2*B,loss_reduction="mean")
        acc=RDPAccountant(); q=min(B/n,1.0); delta=self.delta or 1/(n*np.sqrt(n)); bce=nn.BCEWithLogitsLoss()
        mean=torch.zeros(B,self._embedding_dim); std=mean+1; steps_per_epoch=max(n//B,1); self.epochs_trained=0; self.steps=0; self.stopped_by_budget=False; stop=False
        for ep in range(self.max_epochs):
            for _ in range(steps_per_epoch):
                # stop before a step that would exceed the budget
                acc.history.append((self.sigma,q,1)); e_next=acc.get_epsilon(delta); acc.history.pop()
                if e_next>self.eps_target: stop=True; self.stopped_by_budget=True; break
                c1,m1,col,opt=self._data_sampler.sample_condvec(B); c1=torch.from_numpy(c1); m1=torch.from_numpy(m1)
                perm=np.arange(B); np.random.shuffle(perm)
                real=torch.from_numpy(self._data_sampler.sample_data(X,B,col[perm],opt[perm]).astype("float32")); c2=c1[perm]
                fake=self._apply_activate(self._generator(torch.cat([torch.normal(mean,std),c1],1))).detach()
                inp=torch.cat([torch.cat([real,c2],1),torch.cat([fake,c1],1)]); lab=torch.cat([torch.ones(B),torch.zeros(B)])
                oD.zero_grad(); loss_d=bce(D(inp).squeeze(1),lab); loss_d.backward(); oD.step(); acc.step(noise_multiplier=self.sigma,sample_rate=q)
                c1,m1,col,opt=self._data_sampler.sample_condvec(B); c1=torch.from_numpy(c1); m1=torch.from_numpy(m1)
                fake=self._generator(torch.cat([torch.normal(mean,std),c1],1))
                D.disable_hooks(); y=D(torch.cat([self._apply_activate(fake),c1],1)).squeeze(1)
                loss_g=bce(y,torch.ones(B))+self._cond_loss(fake,c1,m1)
                oG.zero_grad(); loss_g.backward(); oG.step(); D.enable_hooks(); oD.zero_grad(); self.steps+=1
            if stop: break
            self.epochs_trained=ep+1
        self.steps_per_epoch=steps_per_epoch
        self.eps_spent=acc.get_epsilon(delta) if acc.history else 0.0
        return self
