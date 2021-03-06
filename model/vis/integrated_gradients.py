"""
Source:
https://github.com/utkuozbulak/pytorch-cnn-visualizations/blob/master/src/integrated_gradients.py

Modified by Leon Chen
"""

import torch
import numpy as np
from PIL import Image


def convert_to_grayscale(im_as_arr):
    """
        Converts 3d image to grayscale

    Args:
        im_as_arr (numpy arr): RGB image with shape (D,W,H)

    returns:
        grayscale_im (PIL Image)
    """
    grayscale_im = np.sum(np.abs(im_as_arr), axis=0)
    im_max = np.percentile(grayscale_im, 99)
    im_min = np.min(grayscale_im)
    grayscale_im = np.clip((grayscale_im - im_min) / (im_max - im_min), 0, 1)
    grayscale_im = (grayscale_im * 255).astype(np.uint8)
    grayscale_im = Image.fromarray(grayscale_im, mode="L")
    return grayscale_im


class IntegratedGradients:
    """
        Produces gradients generated with integrated gradients from the image
    """

    def __init__(self, model):
        self.model = model
        self.gradients = None
        # Put model in evaluation mode
        self.model.eval()
        # Hook the first layer to get the gradient
        self.hook_layers()

    def hook_layers(self):
        def hook_function(module, grad_in, grad_out):
            self.gradients = grad_in[0]

        # Register hook to the first layer
        first_layer = list(list(self.model.backbone._modules.values())[0]._modules.values())[0]
        first_layer.register_backward_hook(hook_function)

    def generate_images_on_linear_path(self, input_image, steps):
        # Generate uniform numbers between 0 and steps
        step_list = np.arange(steps + 1) / steps
        # Generate scaled xbar images
        xbar_list = [input_image * step for step in step_list]
        return xbar_list

    def generate_gradients(self, input_image, target_class):
        # Forward
        logits, logit_maps = self.model(input_image)
        model_output = torch.cat(logits, dim=1)
        # Zero grads
        self.model.zero_grad()
        # Target for backprop
        one_hot_output = torch.FloatTensor(1, model_output.size()[-1]).zero_()
        one_hot_output[0][target_class] = 1
        if torch.cuda.is_available():
            one_hot_output = one_hot_output.cuda()
        # Backward pass
        model_output.backward(gradient=one_hot_output)
        # Convert Pytorch variable to numpy array
        # [0] to get rid of the first channel (1,3,416,416)
        gradients_as_arr = self.gradients.data.cpu().numpy()[0]
        return gradients_as_arr

    def generate_integrated_gradients(self, input_image, target_class, steps):
        # Generate xbar images
        xbar_list = self.generate_images_on_linear_path(input_image, steps)
        # Initialize an iamge composed of zeros
        integrated_grads = None
        for xbar_image in xbar_list:
            # Generate gradients from xbar images
            single_integrated_grad = self.generate_gradients(xbar_image, target_class)
            if integrated_grads is None:
                integrated_grads = np.zeros(single_integrated_grad.shape)
            # Add rescaled grads from xbar images
            integrated_grads = integrated_grads + single_integrated_grad / steps
        integrated_grads = convert_to_grayscale(integrated_grads)
        return integrated_grads
