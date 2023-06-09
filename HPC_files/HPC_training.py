"""
Program for training the model in HPC.
"""


# Imports

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import rdkit.Chem as Chem
from rdkit.Chem import Draw
from rdkit.Chem import AllChem
import wandb
import random
from mordred import Calculator, descriptors

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split
import torch.optim as optim
import scipy

# wandb.init(project="ai4chem")


def load_data() -> pd.DataFrame:
    """
    Load the data.
    """
    df = pd.read_csv(
        "datasets/mcule_purchasable_in_stock_prices_valid_smiles.csv")
    return df


def generate_molecules(df) -> pd.DataFrame:
    """
    Generate molecules from the SMILES strings.
    """
    df["mol"] = df["SMILES"].apply(lambda x: Chem.MolFromSmiles(x))
    return df


def get_fingerprint(mol):
    """
    Get the fingerprint of a molecule.
    """
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
    arr = np.zeros((1,))
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def calculate_morgan_fp(df) -> pd.DataFrame:
    """
    Calculate the Morgan fingerprint for each molecule in the dataframe.
    """
    df["morgan_fp"] = df["mol"].apply(
        lambda x: AllChem.GetMorganFingerprintAsBitVect(x, 2, nBits=1024))
    return df


def calculate_Mordred_descriptors(df) -> pd.DataFrame:
    """
    Calculate the Mordred descriptors for each molecule in the dataframe.
    """
    calc = Calculator(descriptors, ignore_3D=False)
    df_features = df["mol"].apply(lambda x: calc(x))
    return df_features


class MultipleLinearRegression(torch.nn.Module):
    def __init__(self, input_dim, output_dim=1):
        super().__init__()
        self.linear = torch.nn.Linear(input_dim, output_dim)
    # Prediction

    def forward(self, x):
        y_pred = self.linear(x)
        return y_pred


def train_simplest_regre_net(df_X, df_y,
                             seed, y_name="Price", y_unit="USD", batch_size=32, lr=0.01, nb_epochs=100, print_epochs=True):
    random.seed(seed)
    np.random.seed(seed)
    torch.random.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    X_tensor = torch.tensor(df_X.values, dtype=torch.float32)
    y_tensor = torch.tensor(df_y.values, dtype=torch.float32)
    y_tensor = y_tensor[:, None]  # Good dimension for the tgt

    dataset = TensorDataset(X_tensor, y_tensor)

    """
    t_v_t = [0.8,0.2,0]
    train_size = int(len(dataset)*t_v_t[0])
    val_size = int(len(dataset)*t_v_t[1])
    test_size = len(dataset)- train_size -val_size
    tensor_train_dataset, tensor_valid_dataset, tensor_test_dataset = random_split(dataset,[train_size,val_size,test_size])
    """
    train_over_all_data = 0.8
    train_size = int(len(dataset)*train_over_all_data)
    test_size = int(len(dataset)-len(dataset)*(train_over_all_data))
    tensor_train_dataset, tensor_test_dataset = random_split(
        dataset, [train_size, test_size])

    train_dataset = DataLoader(
        tensor_train_dataset, batch_size=batch_size, shuffle=True)
    test_dataset = DataLoader(
        tensor_test_dataset, batch_size=batch_size, shuffle=False)

    model = MultipleLinearRegression(input_dim=X_tensor.shape[1])

    criterion = torch.nn.MSELoss()
    optimizer = optim.SGD(model.parameters(), lr=lr)
    running_loss = 0.0

    for epoch in range(nb_epochs):
        for i, data in enumerate(train_dataset, 0):
            batch_per_epoch = len(train_dataset)
            # get the inputs; data is a list of [inputs, labels]
            inputs, labels = data
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            # print statistics
            running_loss += loss.item()
            if i % batch_per_epoch == batch_per_epoch-1:    # print every last mini-batch of an epoch
                if print_epochs:
                    print(
                        f'[{epoch + 1}, {i + 1:5d}] loss: {running_loss / batch_per_epoch:.3f}')
                running_loss = 0.0
    print('Finished Training')

    number_batch = 0
    total_loss = 0
    with torch.no_grad():
        for i, data in enumerate(test_dataset, 0):
            inputs, labels = data
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            total_loss += loss.item()
            number_batch += 1
        print(
            f'MSE Loss of the network on test set is {total_loss/number_batch}')
        print(
            f'MAE Loss of the network on test set is {(total_loss/number_batch)**0.5}')

    for i, data in enumerate(test_dataset):
        inputs, labels = data
        outputs = model(inputs)
        # print(outputs.shape)
        if i == 0:
            true_tgt = labels
            pred_tgt = outputs
        else:
            pred_tgt = torch.cat((pred_tgt, outputs), 0)
            true_tgt = torch.cat((true_tgt, labels), 0)
    min_label = torch.min(true_tgt)
    max_label = torch.max(true_tgt)
    print(f"min value is {min_label}")
    print(f"max value is {max_label}")
    print(f"max-min is {max_label-min_label}")
    pred_tgt = torch.squeeze(pred_tgt).detach().numpy()
    true_tgt = torch.squeeze(true_tgt).detach().numpy()
    # plt.hexbin(true_tgt,pred_tgt)
    plt.scatter(true_tgt, pred_tgt, marker='.',
                label="datapoint", color="#007480")
    plt.plot([min_label, max_label], [min_label, max_label],
             label="pred=true", color='k')
    plt.xlabel(f"Computed {y_name} [{y_unit}]")
    plt.ylabel(f"Predicted {y_name} [{y_unit}]")
    plt.legend()
    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(
        true_tgt, pred_tgt)
    r2 = r_value**2
    plt.title(
        f"MAE: {(total_loss/number_batch)**0.5:.2f}, mean: {true_tgt.mean():.2f}, $R^2$: {r2:.2f}")
    plt.savefig(f"HPC_output/regre_{'_'.join(y_name.split())}.pdf")
    plt.show()
    return (total_loss)


if __name__ == "__main__":
    print("Loading dataset ...")
    # df = pd.read_csv(
    #    "datasets/mcule_purchasable_in_stock_prices_valid_smiles.csv")

    # print("Dataset loaded")

    df = pd.read_csv("datasets/mordred_descriptors.csv")
    df_X = df[[k for k in df.columns if k != "price 1 (USD)"]]
    # take the last columns
    df_y = df["price 1 (USD)"]

    # create molecules

    # df["mol"] = df["SMILES"].apply(lambda x: Chem.MolFromSmiles(x))

    # calculate the morgan fingerprints
    # df = calculate_morgan_fp(df)

    # make a df with the target
    # df_y = df[["price 1 (USD)"]].astype(float)

    # for fp_bit in range(2048):
    #    df[f"fp_bit_{fp_bit}"] = df["morgan_fp"].apply(
    #        lambda x: float(x[fp_bit]))

    # df_X = df[[f"fp_bit_{fp_bit}" for fp_bit in range(2048)]]

    print(df_X.astype(dtype=float))
    print(df_y.astype(dtype=float))

    # train the model
    train_simplest_regre_net(df_X, df_y, seed=0, y_name="price 1 (USD)",
                             y_unit="USD", batch_size=32, lr=0.01, nb_epochs=100, print_epochs=True)
