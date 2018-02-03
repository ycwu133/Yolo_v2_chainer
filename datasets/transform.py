#!/usr/env/bin python3
# -*- coding: utf-8 -*-

import argparse
import numpy as np
import sys
import subprocess
import os
import yaml

import chainer
from chainer.datasets import TransformDataset
from chainercv import transforms
from chainercv.links.model.ssd import random_crop_with_bbox_constraints
from chainercv.links.model.ssd import random_distort
from chainercv.links.model.ssd import resize_with_random_interpolation

class Transform(object):

    def __init__(self, coder, shape, value, max_target=30):
        # to send cpu, make a copy
        # self.coder = copy.copy(coder)
        # self.coder.to_cpu()

        self.output_shape = shape
        self.value = value
        self.max_target = max_target

    def __call__(self, in_data):
        """in_data includes three datas.
        Args:
            img(array): Shape is (3, H, W). range is [0, 255].
            bbox(array): Shape is (N, 4). (y_min, x_min, y_max, x_max).
                         range is [0, max size of boxes].
            label(array): Classes of bounding boxes.

        Returns:
            img(array): Shape is (3, out_H, out_W). range is [0, 1].
                        interpolation value equals to self.value.
        """
        # Darknet
        # jitterは新しいresizeの値をrandomに決める機構(new_rate)
        # hがその時点で大きいなら、h = h * scale, w = h * new_rate
        # place_imageは、resizeもかねて行われる。範囲外は代入されない.
        # 真ん中に画像を置くのではなく、randomに配置する.

        # There are five data augmentation steps
        # 1. Color augmentation
        # 2. Random expansion
        # 3. Random cropping
        # 4. Resizing with random interpolation
        # 5. Random horizontal flipping

        img, bbox, label = in_data

        # 1. Color augmentation
        img = random_distort(img, brightness_delta=32,
                             contrast_low=0.5, contrast_high=1.5,
                             saturation_low=0.5, saturation_high=1.5,
                             hue_delta=25)

        # Normalize. range is [0, 1]
        img /= 255.0

        orig_shape = img.shape[1:]

        # 2. Random expansion: resize and translation. 拡大だけしかしない？
        output_img = np.zeros((3, self.output_shape[0], self.output_shape[1]),
                               dtype='f') + 0.5
        # if np.random.randint(2):
        img, param = transforms.random_expand(
                         img, max_ratio=2, fill=self.value, return_param=True)
        bbox = transforms.translate_bbox(
            bbox, y_offset=param['y_offset'], x_offset=param['x_offset'])
        left_x = param['x_offset']
        right_x = left_x + orig_shape[1]
        top_y = param['y_offset']
        bottom_y = top_y + orig_shape[0]

        # 3. Random cropping
        img, param = random_crop_with_bbox_constraints(
            img, bbox, return_param=True)

        crop_shape = img.shape[1:]
        left_x = max(0, left_x - param['x_slice'].start)
        right_x = min(param['x_slice'].stop, right_x)
        top_y = max(0, top_y - param['y_slice'].start)
        bottom_y = min(param['y_slice'].stop, bottom_y)
        x_slice = slice(left_x, right_x)
        y_slice = slice(top_y, bottom_y)
        # x_slice = param['x_slice']

        bbox, param = transforms.crop_bbox(
            bbox, y_slice=param['y_slice'], x_slice=param['x_slice'],
            allow_outside_center=False, return_param=True)
        label = label[param['index']]

        # 4. Resizing with random interpolatation # TODO
        _, H, W = img.shape
        # h_rate = self.output_shape[0] / H
        # w_rate = self.output_shape[1] / W
        # x_slice = slice(int(left_x * w_rate), int(right_x * w_rate))
        # y_slice = slice(int(top_y * h_rate), int(bottom_y * h_rate))
        # hoge = resize_with_random_interpolation(img, self.output_shape)
        # output_img[:, y_slice, x_slice] = hoge[:, y_slice, x_slice]

        # import matplotlib.pyplot as plt
        # plt.imshow(output_img.transpose(1, 2, 0))
        # plt.show()

        img = resize_with_random_interpolation(img, self.output_shape)
        bbox = transforms.resize_bbox(bbox, (H, W), self.output_shape)

        # import matplotlib.pyplot as plt
        # plt.imshow(img.transpose(1, 2, 0))
        # plt.show()

        # 5. Random horizontal flipping # OK
        img, params = transforms.random_flip(
                          img, x_random=True, return_param=True)
        bbox = transforms.flip_bbox(
                   bbox, self.output_shape, x_flip=params['x_flip'])

        # Preparation for Yolov2 network

        # Range of bounding box is [0, 1]
        bbox[:, ::2] /= self.output_shape[0]
        bbox[:, 1::2] /= self.output_shape[1]

        return img, mb_loc, mb_label