import torch.nn as nn
from ..config import MODEL_DIR
from ..utils import Head,Model
from torch.autograd import Variable
################################################## Model: ResNet50 ############################################

class ResNet50():
    def __init__(self, opt):
        self._opt = opt
        self._name = 'ResNet50'
        self._output_size_per_task = {'AU': self._opt.AU_label_size, 'EXPR': self._opt.EXPR_label_size, 'VA': self._opt.VA_label_size * self._opt.digitize_num}
        # create networks
        self._init_create_networks()

    def _init_create_networks(self):
        """
        init current model according to sofar tasks
        """
        backbone = BackBone(self._opt)
        output_sizes = [self._output_size_per_task[x] for x in self._opt.tasks]
        output_feature_dim = backbone.output_feature_dim
        classifiers = [Head(output_feature_dim, self._opt.hidden_size, output_sizes[i]) for i in range(len(self._opt.tasks))]
        classifiers = nn.ModuleList(classifiers)
        self.resnet50 = Model(backbone, classifiers, self._opt.tasks)
        if len(self._opt.gpu_ids) > 1:
            self.resnet50 = torch.nn.DataParallel(self.resnet50, device_ids=self._opt.gpu_ids)
        self.resnet50.cuda()
    def load(self, model_path):
        self.resnet50.load_state_dict(torch.load(model_path))  

    def set_eval(self):
        self.resnet50.eval()
        self._is_train = False

    def forward(self, input_image = None):
        assert self._is_train is False, "Model must be in eval mode"
        with torch.no_grad():
            input_image = Variable(input_image)
            if not input_image.is_cuda:
                input_image = input_image.cuda()
            output = self.resnet50(input_image)
            out_dict = self._format_estimates(output['output'])
            out_dict_raw = dict([(key,output['output'][key]) for key in output['output'].keys()])
        return out_dict, out_dict_raw
    def _format_estimates(self, output):
        estimates = {}
        for task in output.keys():
            if task == 'AU':
                o = (torch.sigmoid(output['AU'].cpu())>0.5).type(torch.LongTensor)
                estimates['AU'] = o.numpy()
            elif task == 'EXPR':
                o = F.softmax(output['EXPR'].cpu(), dim=-1).argmax(-1).type(torch.LongTensor)
                estimates['EXPR'] = o.numpy()
            elif task == 'VA':
                N = self._opt.digitize_num
                v = F.softmax(output['VA'][:, :N].cpu(), dim=-1).numpy()
                a = F.softmax(output['VA'][:, N:].cpu(), dim=-1).numpy()
                bins = np.linspace(-1, 1, num=self._opt.digitize_num)
                v = (bins * v).sum(-1)
                a = (bins * a).sum(-1)
                estimates['VA'] = np.stack([v, a], axis = 1)
        return estimates
