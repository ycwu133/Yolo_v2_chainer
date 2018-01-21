#!/usr/env/bin python3
# -*- coding: utf-8 -*-

import argparse
import numpy as np
import sys
import subprocess
import os
import yaml

import chainer
from chainer import cuda, optimizers, serializers
from chainer import training

from config_utils import *

chainer.cuda.set_max_workspace_size(1024 * 1024 * 1024)
os.environ["CHAINER_TYPE_CHECK"] = "0"

from collections import OrderedDict
yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    lambda loader, node: OrderedDict(loader.construct_pairs(node)))

def train_yolov2():
    """Training yolov2."""
    config = parse_args()
    devices = parse_devices(config['gpus'], config['updater']['name'])
    train_data, test_data = load_dataset(config["dataset"])
    train_iter, test_iter = create_iterator(train_data, test_data,
                                            config['iterator'], devices,
                                            config['updater']['name'])
    model = get_model(config["model"])
    optimizer = create_optimizer(config['optimizer'], model)
    updater = create_updater(train_iter, optimizer, config['updater'], devices)
    trainer = training.Trainer(updater, config['end_trigger'], out=config['results'])
    trainer = create_extension(trainer, test_iter,  model,
                               config['extension'], devices=devices)
    trainer.run()
    chainer.serializers.save_npz(os.path.join(config['results'], 'model.npz'),
                                 model)

def main():
    train_yolov2()

if __name__ == '__main__':
    main()
