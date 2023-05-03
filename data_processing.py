import numpy as np
import matplotlib.pyplot as plt
import torch
#from torchvision import transforms, datasets
#import sklearn
import pandas as pd
import rdkit
import random

torch.manual_seed(0)
torch.cuda.manual_seed(0)
np.random.seed(0)
random.seed(0)

data=pd.read_csv("mcule_purchasable_in_stock_prices_230324_RKoqmy.csv", delimiter=",", low_memory=False)
print(data.head())